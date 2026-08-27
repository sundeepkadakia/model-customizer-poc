from __future__ import annotations

import csv
import io
import json
import random
import sqlite3
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ADAPTERS = ROOT / "adapters"
DB_PATH = ROOT / "model_customizer.sqlite3"
DATA.mkdir(exist_ok=True)
ADAPTERS.mkdir(exist_ok=True)

app = FastAPI(title="Model Customizer MVP", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with DB_LOCK, connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                goal TEXT NOT NULL,
                base_model TEXT NOT NULL,
                status TEXT NOT NULL,
                dataset_format TEXT,
                example_count INTEGER DEFAULT 0,
                train_count INTEGER DEFAULT 0,
                eval_count INTEGER DEFAULT 0,
                dataset_dir TEXT,
                adapter_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                log TEXT DEFAULT '',
                result_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


init_db()


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=3, max_length=1000)
    base_model: str = "Qwen/Qwen3-4B"


class TrainRequest(BaseModel):
    epochs: int = Field(default=1, ge=1, le=10)
    learning_rate: float = Field(default=2e-4, gt=0, le=0.01)
    lora_rank: int = Field(default=4, ge=1, le=64)
    max_length: int = Field(default=128, ge=64, le=4096)


class CompareRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    max_new_tokens: int = Field(default=50, ge=1, le=1024)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    max_new_tokens: int = Field(default=80, ge=1, le=1024)


INPUT_ALIASES = [
    "prompt", "input", "question", "query", "user", "user_message",
    "customer_message", "ticket", "request", "instruction",
]
OUTPUT_ALIASES = [
    "response", "output", "answer", "completion", "ideal_response",
    "assistant", "assistant_response", "agent_reply", "best_rep_response",
]
CONVERSATION_ALIASES = ["messages", "conversation", "chat", "turns"]
SYSTEM_ALIASES = ["system", "system_prompt", "instructions"]


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def get_project(project_id: str) -> dict:
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Project not found")
    return dict(row)


def update_project(project_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now_iso()
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [project_id]
    with DB_LOCK, connect_db() as conn:
        conn.execute(f"UPDATE projects SET {columns} WHERE id = ?", values)


def create_job(project_id: str, kind: str) -> dict:
    job_id = str(uuid.uuid4())
    ts = now_iso()
    with DB_LOCK, connect_db() as conn:
        conn.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, project_id, kind, "queued", ts, ts),
        )
    return get_job_row(job_id)


def get_job_row(job_id: str) -> dict:
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    result = dict(row)
    if result.get("result_json"):
        try:
            result["result"] = json.loads(result["result_json"])
        except json.JSONDecodeError:
            result["result"] = None
    result.pop("result_json", None)
    return result


def update_job(job_id: str, *, status: str | None = None, log: str | None = None, result: dict | None = None) -> None:
    fields: Dict[str, Any] = {"updated_at": now_iso()}
    if status is not None:
        fields["status"] = status
    if log is not None:
        fields["log"] = log[-12000:]
    if result is not None:
        fields["result_json"] = json.dumps(result)
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [job_id]
    with DB_LOCK, connect_db() as conn:
        conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)


def parse_upload(filename: str, raw: bytes) -> list[dict]:
    suffix = Path(filename or "dataset.jsonl").suffix.lower()
    text = raw.decode("utf-8-sig")

    try:
        if suffix == ".csv":
            return [dict(row) for row in csv.DictReader(io.StringIO(text))]

        if suffix == ".json":
            obj = json.loads(text)
            if isinstance(obj, list):
                return obj
            if isinstance(obj, dict):
                for key in ("data", "examples", "records", "items"):
                    if isinstance(obj.get(key), list):
                        return obj[key]
                return [obj]
            raise ValueError("JSON root must be an object or array")

        # JSONL is the default, including unknown extensions.
        rows = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
        return rows
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(400, f"Could not parse dataset: {exc}") from exc


def first_present(row: dict, candidates: Iterable[str]) -> str | None:
    lower_map = {str(k).lower(): k for k in row.keys()}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return str(lower_map[candidate.lower()])
    return None


def normalize_messages(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("Conversation field must be a list")
    normalized = []
    for i, message in enumerate(value):
        if not isinstance(message, dict):
            raise ValueError(f"Conversation item {i + 1} must be an object")
        role = message.get("role") or message.get("speaker") or message.get("from")
        content = message.get("content") or message.get("text") or message.get("message")
        if not isinstance(role, str) or not isinstance(content, str):
            raise ValueError(f"Conversation item {i + 1} needs role/speaker and content/text")
        role_lower = role.lower().strip()
        role_map = {
            "human": "user", "customer": "user", "client": "user",
            "bot": "assistant", "agent": "assistant", "model": "assistant", "ai": "assistant",
        }
        role_lower = role_map.get(role_lower, role_lower)
        if role_lower not in {"system", "user", "assistant"}:
            raise ValueError(f"Unsupported conversation role '{role}'")
        normalized.append({"role": role_lower, "content": content.strip()})

    if not any(m["role"] == "user" for m in normalized) or not any(m["role"] == "assistant" for m in normalized):
        raise ValueError("Each conversation needs at least one user and one assistant message")
    return normalized


def normalize_rows(
    rows: list[dict],
    mode: Literal["auto", "prompt_response", "conversation"],
    prompt_field: str | None,
    response_field: str | None,
) -> tuple[list[dict], dict]:
    if not rows:
        raise HTTPException(400, "Dataset is empty")
    if not all(isinstance(row, dict) for row in rows):
        raise HTTPException(400, "Every dataset record must be an object/row")

    sample = rows[0]
    conversation_field = first_present(sample, CONVERSATION_ALIASES)
    detected_mode = mode
    if mode == "auto":
        detected_mode = "conversation" if conversation_field else "prompt_response"

    normalized = []
    mapping: dict[str, Any] = {"mode": detected_mode}

    if detected_mode == "conversation":
        conversation_field = conversation_field or first_present(sample, CONVERSATION_ALIASES)
        if not conversation_field:
            raise HTTPException(400, f"Could not find a conversation field. Try one of: {', '.join(CONVERSATION_ALIASES)}")
        mapping["conversation_field"] = conversation_field
        for idx, row in enumerate(rows, start=1):
            try:
                messages = normalize_messages(row.get(conversation_field))
            except ValueError as exc:
                raise HTTPException(400, f"Row {idx}: {exc}") from exc
            normalized.append({"messages": messages, "metadata": {"source_row": idx}})
    else:
        p_field = prompt_field or first_present(sample, INPUT_ALIASES)
        r_field = response_field or first_present(sample, OUTPUT_ALIASES)
        if not p_field or not r_field:
            raise HTTPException(
                400,
                "Could not infer prompt/response columns. Provide field names explicitly. "
                f"Prompt aliases: {', '.join(INPUT_ALIASES)}. Response aliases: {', '.join(OUTPUT_ALIASES)}.",
            )
        mapping.update(prompt_field=p_field, response_field=r_field)
        sys_field = first_present(sample, SYSTEM_ALIASES)
        if sys_field:
            mapping["system_field"] = sys_field

        for idx, row in enumerate(rows, start=1):
            prompt = row.get(p_field)
            response = row.get(r_field)
            if not isinstance(prompt, str) or not prompt.strip():
                raise HTTPException(400, f"Row {idx}: '{p_field}' must contain text")
            if not isinstance(response, str) or not response.strip():
                raise HTTPException(400, f"Row {idx}: '{r_field}' must contain text")
            messages = []
            if sys_field and isinstance(row.get(sys_field), str) and row.get(sys_field).strip():
                messages.append({"role": "system", "content": row[sys_field].strip()})
            messages.extend([
                {"role": "user", "content": prompt.strip()},
                {"role": "assistant", "content": response.strip()},
            ])
            normalized.append({"messages": messages, "metadata": {"source_row": idx}})

    return normalized, mapping


def split_examples(rows: list[dict], eval_ratio: float = 0.2) -> tuple[list[dict], list[dict]]:
    if len(rows) < 10:
        raise HTTPException(400, "MVP requires at least 10 examples so we can keep a held-out evaluation set")
    shuffled = rows[:]
    random.Random(42).shuffle(shuffled)
    eval_count = max(2, round(len(shuffled) * eval_ratio))
    eval_count = min(eval_count, len(shuffled) - 1)
    return shuffled[eval_count:], shuffled[:eval_count]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def run_job(job_id: str, cmd: list[str], *, project_id: str, kind: str, on_success=None) -> None:
    update_job(job_id, status="running")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode != 0:
            update_job(job_id, status="failed", log=combined)
            if kind == "training":
                update_project(project_id, status="training_failed")
            return

        result = None
        if kind in {"evaluation"}:
            # Evaluation scripts print JSON as their final stdout payload.
            lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
            if lines:
                result = json.loads(lines[-1])
        update_job(job_id, status="completed", log=combined, result=result)
        if on_success:
            on_success()
    except Exception as exc:  # keep background worker failures observable through /jobs
        update_job(job_id, status="failed", log=f"{type(exc).__name__}: {exc}")
        if kind == "training":
            update_project(project_id, status="training_failed")


@app.get("/health")
def health():
    return {"ok": True, "database": str(DB_PATH), "version": app.version}


@app.get("/projects")
def list_projects():
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/projects/{project_id}")
def project_detail(project_id: str):
    return get_project(project_id)


@app.post("/projects")
def create_project(req: ProjectCreate):
    pid = str(uuid.uuid4())
    ts = now_iso()
    with DB_LOCK, connect_db() as conn:
        conn.execute(
            """INSERT INTO projects
               (id, name, goal, base_model, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pid, req.name, req.goal, req.base_model, "created", ts, ts),
        )
    return get_project(pid)


@app.post("/projects/{project_id}/dataset")
async def upload_dataset(
    project_id: str,
    file: UploadFile = File(...),
    mode: Literal["auto", "prompt_response", "conversation"] = Form("auto"),
    prompt_field: str | None = Form(None),
    response_field: str | None = Form(None),
):
    get_project(project_id)
    raw_rows = parse_upload(file.filename or "dataset.jsonl", await file.read())
    normalized, mapping = normalize_rows(raw_rows, mode, prompt_field or None, response_field or None)
    train_rows, eval_rows = split_examples(normalized)

    project_dir = DATA / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = project_dir / "normalized.jsonl"
    train_path = project_dir / "train.jsonl"
    eval_path = project_dir / "eval.jsonl"
    write_jsonl(normalized_path, normalized)
    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, eval_rows)
    (project_dir / "dataset_manifest.json").write_text(
        json.dumps({
            "source_filename": file.filename,
            "mapping": mapping,
            "examples": len(normalized),
            "train_examples": len(train_rows),
            "eval_examples": len(eval_rows),
        }, indent=2),
        encoding="utf-8",
    )

    update_project(
        project_id,
        status="dataset_ready",
        dataset_format=mapping["mode"],
        example_count=len(normalized),
        train_count=len(train_rows),
        eval_count=len(eval_rows),
        dataset_dir=str(project_dir),
    )
    return {
        "project_id": project_id,
        "examples": len(normalized),
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "detected": mapping,
        "preview": normalized[:2],
    }


@app.post("/projects/{project_id}/train")
def train(project_id: str, req: TrainRequest):
    project = get_project(project_id)
    if not project.get("dataset_dir"):
        raise HTTPException(400, "Upload a dataset first")

    dataset = Path(project["dataset_dir"]) / "train.jsonl"
    output_dir = ADAPTERS / project_id
    job = create_job(project_id, "training")
    cmd = [
        sys.executable,
        str(ROOT / "training" / "train_lora.py"),
        "--model", project["base_model"],
        "--dataset", str(dataset),
        "--output", str(output_dir),
        "--epochs", str(req.epochs),
        "--lr", str(req.learning_rate),
        "--rank", str(req.lora_rank),
        "--max-length", str(req.max_length),
    ]

    update_project(project_id, status="training")

    def success():
        update_project(project_id, status="trained", adapter_path=str(output_dir))

    threading.Thread(
        target=run_job,
        args=(job["id"], cmd),
        kwargs={"project_id": project_id, "kind": "training", "on_success": success},
        daemon=True,
    ).start()
    return get_job_row(job["id"])


@app.post("/projects/{project_id}/evaluate")
def evaluate(project_id: str):
    project = get_project(project_id)
    if not project.get("adapter_path"):
        raise HTTPException(400, "Train the project first")
    eval_path = Path(project["dataset_dir"]) / "eval.jsonl"
    job = create_job(project_id, "evaluation")
    cmd = [
        sys.executable,
        str(ROOT / "training" / "evaluate.py"),
        "--model", project["base_model"],
        "--adapter", project["adapter_path"],
        "--dataset", str(eval_path),
        "--max-new-tokens", "50",
    ]
    threading.Thread(
        target=run_job,
        args=(job["id"], cmd),
        kwargs={"project_id": project_id, "kind": "evaluation"},
        daemon=True,
    ).start()
    return get_job_row(job["id"])


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    return get_job_row(job_id)


@app.post("/projects/{project_id}/compare")
def compare(project_id: str, req: CompareRequest):
    project = get_project(project_id)
    if not project.get("adapter_path"):
        raise HTTPException(400, "Train the project first")

    cmd = [
        sys.executable,
        str(ROOT / "training" / "compare.py"),
        "--model", project["base_model"],
        "--adapter", project["adapter_path"],
        "--prompt", req.prompt,
        "--max-new-tokens", str(req.max_new_tokens),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise HTTPException(500, detail={"message": "Comparison failed", "stderr": proc.stderr[-8000:]})
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise HTTPException(500, detail={"message": "Comparison returned invalid output", "stdout": proc.stdout[-4000:]}) from exc


@app.post("/projects/{project_id}/generate")
def generate(project_id: str, req: GenerateRequest):
    project = get_project(project_id)
    if not project.get("adapter_path"):
        raise HTTPException(400, "Train the project first")
    cmd = [
        sys.executable,
        str(ROOT / "training" / "generate.py"),
        "--model", project["base_model"],
        "--adapter", project["adapter_path"],
        "--prompt", req.prompt,
        "--max-new-tokens", str(req.max_new_tokens),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise HTTPException(500, detail={"message": "Generation failed", "stderr": proc.stderr[-8000:]})
    return json.loads(proc.stdout.strip().splitlines()[-1])
