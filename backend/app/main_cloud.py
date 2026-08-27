from __future__ import annotations

import csv
import io
import json
import os
import random
import uuid
from pathlib import Path
from typing import Any, Iterable, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_FILE)

from .cloud import FirestoreRepo, GCSStore, RunPodClient, now_iso

app = FastAPI(title="Model Customizer Cloud API", version="0.3.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
repo = FirestoreRepo()
store = GCSStore()


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=3, max_length=1000)
    base_model: str = "Qwen/Qwen3-4B"


class TrainRequest(BaseModel):
    epochs: int = Field(default=1, ge=1, le=10)
    learning_rate: float = Field(default=2e-4, gt=0, le=0.01)
    lora_rank: int = Field(default=8, ge=1, le=64)
    max_length: int = Field(default=512, ge=64, le=4096)


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    max_new_tokens: int = Field(default=100, ge=1, le=1024)


INPUT_ALIASES = ["prompt","input","question","query","user","user_message","customer_message","ticket","request","instruction"]
OUTPUT_ALIASES = ["response","output","answer","completion","ideal_response","assistant","assistant_response","agent_reply","best_rep_response"]
CONVERSATION_ALIASES = ["messages","conversation","chat","turns"]
SYSTEM_ALIASES = ["system","system_prompt","instructions"]


def get_project(pid: str) -> dict:
    x = repo.get_project(pid)
    if not x: raise HTTPException(404, "Project not found")
    return x


def create_job(pid: str, kind: str, payload: dict) -> dict:
    jid = str(uuid.uuid4()); ts = now_iso()
    remote = RunPodClient().run_async(payload)
    job = {"id": jid, "project_id": pid, "kind": kind, "status": "queued", "provider": "runpod", "provider_job_id": remote["id"], "created_at": ts, "updated_at": ts}
    return repo.create_job(job)


def parse_upload(filename: str, raw: bytes) -> list[dict]:
    suffix = Path(filename or "dataset.jsonl").suffix.lower(); text = raw.decode("utf-8-sig")
    if suffix == ".csv": return [dict(r) for r in csv.DictReader(io.StringIO(text))]
    if suffix == ".json":
        obj = json.loads(text)
        if isinstance(obj, list): return obj
        if isinstance(obj, dict):
            for k in ("data","examples","records","items"):
                if isinstance(obj.get(k), list): return obj[k]
            return [obj]
    rows=[]
    for n,line in enumerate(text.splitlines(),1):
        if line.strip():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError as e: raise HTTPException(400, f"Invalid JSON on line {n}: {e}")
    return rows


def first_present(row: dict, candidates: Iterable[str]) -> str | None:
    m={str(k).lower():k for k in row}
    for c in candidates:
        if c.lower() in m: return str(m[c.lower()])
    return None


def normalize_messages(value: Any) -> list[dict]:
    if not isinstance(value,list): raise ValueError("Conversation field must be a list")
    out=[]
    role_map={"human":"user","customer":"user","client":"user","bot":"assistant","agent":"assistant","model":"assistant","ai":"assistant"}
    for i,m in enumerate(value):
        if not isinstance(m,dict): raise ValueError(f"Conversation item {i+1} must be an object")
        role=m.get("role") or m.get("speaker") or m.get("from"); content=m.get("content") or m.get("text") or m.get("message")
        if not isinstance(role,str) or not isinstance(content,str): raise ValueError(f"Conversation item {i+1} needs role and content")
        role=role_map.get(role.lower().strip(),role.lower().strip())
        if role not in {"system","user","assistant"}: raise ValueError(f"Unsupported role {role}")
        out.append({"role":role,"content":content.strip()})
    if not any(x["role"]=="user" for x in out) or not any(x["role"]=="assistant" for x in out): raise ValueError("Conversation needs user and assistant messages")
    return out


def normalize_rows(rows: list[dict], mode: str, prompt_field: str|None, response_field: str|None):
    if not rows or not all(isinstance(r,dict) for r in rows): raise HTTPException(400,"Dataset must contain object rows")
    sample=rows[0]; conversation_field=first_present(sample,CONVERSATION_ALIASES)
    detected = ("conversation" if conversation_field else "prompt_response") if mode=="auto" else mode
    normalized=[]; mapping={"mode":detected}
    if detected=="conversation":
        field=conversation_field or first_present(sample,CONVERSATION_ALIASES)
        if not field: raise HTTPException(400,"Could not find conversation/messages field")
        mapping["conversation_field"]=field
        for i,row in enumerate(rows,1):
            try: messages=normalize_messages(row.get(field))
            except ValueError as e: raise HTTPException(400,f"Row {i}: {e}")
            normalized.append({"messages":messages,"metadata":{"source_row":i}})
    else:
        pf=prompt_field or first_present(sample,INPUT_ALIASES); rf=response_field or first_present(sample,OUTPUT_ALIASES); sf=first_present(sample,SYSTEM_ALIASES)
        if not pf or not rf: raise HTTPException(400,"Could not infer prompt/response columns; provide mappings explicitly")
        mapping.update(prompt_field=pf,response_field=rf)
        if sf: mapping["system_field"]=sf
        for i,row in enumerate(rows,1):
            p=row.get(pf); r=row.get(rf)
            if not isinstance(p,str) or not p.strip() or not isinstance(r,str) or not r.strip(): raise HTTPException(400,f"Row {i}: prompt and response must contain text")
            messages=[]
            if sf and isinstance(row.get(sf),str) and row[sf].strip(): messages.append({"role":"system","content":row[sf].strip()})
            messages += [{"role":"user","content":p.strip()},{"role":"assistant","content":r.strip()}]
            normalized.append({"messages":messages,"metadata":{"source_row":i}})
    return normalized,mapping


def split_examples(rows: list[dict]):
    if len(rows)<10: raise HTTPException(400,"At least 10 examples are required so evaluation can stay held out")
    xs=rows[:]; random.Random(42).shuffle(xs); n=max(2,round(len(xs)*0.2)); return xs[n:],xs[:n]


def jsonl(rows: list[dict]) -> str:
    return "\n".join(json.dumps(x,ensure_ascii=False) for x in rows)+"\n"


@app.get("/health")
def health(): return {"ok":True,"version":app.version,"storage":"gcs","database":"firestore","gpu":"runpod"}

@app.get("/projects")
def projects(): return repo.list_projects()

@app.get("/projects/{pid}")
def project(pid:str): return get_project(pid)

@app.post("/projects")
def create_project(req: ProjectCreate):
    pid=str(uuid.uuid4()); ts=now_iso(); doc={"id":pid,"name":req.name,"goal":req.goal,"base_model":req.base_model,"status":"created","created_at":ts,"updated_at":ts}
    return repo.create_project(doc)

@app.post("/projects/{pid}/dataset")
async def upload_dataset(pid:str,file:UploadFile=File(...),mode:Literal["auto","prompt_response","conversation"]=Form("auto"),prompt_field:str|None=Form(None),response_field:str|None=Form(None)):
    get_project(pid); raw=await file.read(); rows=parse_upload(file.filename or "dataset.jsonl",raw); normalized,mapping=normalize_rows(rows,mode,prompt_field,response_field); train,evals=split_examples(normalized)
    prefix=f"projects/{pid}/datasets/current"
    raw_uri=store.upload_bytes(f"{prefix}/source/{file.filename or 'dataset'}",raw,file.content_type or "application/octet-stream")
    normalized_uri=store.upload_text(f"{prefix}/normalized.jsonl",jsonl(normalized),"application/x-ndjson")
    train_uri=store.upload_text(f"{prefix}/train.jsonl",jsonl(train),"application/x-ndjson")
    eval_uri=store.upload_text(f"{prefix}/eval.jsonl",jsonl(evals),"application/x-ndjson")
    manifest={"source_filename":file.filename,"raw_uri":raw_uri,"normalized_uri":normalized_uri,"train_uri":train_uri,"eval_uri":eval_uri,"mapping":mapping,"examples":len(normalized),"train_examples":len(train),"eval_examples":len(evals)}
    store.upload_text(f"{prefix}/manifest.json",json.dumps(manifest,indent=2))
    repo.update_project(pid,status="dataset_ready",dataset=manifest,example_count=len(normalized),train_count=len(train),eval_count=len(evals))
    return {**manifest,"preview":normalized[:2]}

@app.post("/projects/{pid}/train")
def train(pid:str,req:TrainRequest):
    p=get_project(pid); dataset=p.get("dataset") or {}
    if not dataset.get("train_uri"): raise HTTPException(400,"Upload a dataset first")
    adapter_prefix=f"gs://{store.bucket_name}/projects/{pid}/adapters/current"
    payload={"task":"train","project_id":pid,"model":p["base_model"],"dataset_uri":dataset["train_uri"],"adapter_uri":adapter_prefix,"epochs":req.epochs,"learning_rate":req.learning_rate,"lora_rank":req.lora_rank,"max_length":req.max_length}
    job=create_job(pid,"training",payload); repo.update_project(pid,status="training",pending_adapter_uri=adapter_prefix); return job

@app.post("/projects/{pid}/evaluate")
def evaluate(pid:str):
    p=get_project(pid); adapter=p.get("adapter_uri"); dataset=p.get("dataset") or {}
    if not adapter: raise HTTPException(400,"Train the project first")
    return create_job(pid,"evaluation",{"task":"evaluate","model":p["base_model"],"adapter_uri":adapter,"dataset_uri":dataset["eval_uri"],"max_new_tokens":50})

@app.post("/projects/{pid}/compare")
def compare(pid:str,req:PromptRequest):
    p=get_project(pid)
    if not p.get("adapter_uri"): raise HTTPException(400,"Train the project first")
    return create_job(pid,"comparison",{"task":"compare","model":p["base_model"],"adapter_uri":p["adapter_uri"],"prompt":req.prompt,"max_new_tokens":req.max_new_tokens})

@app.post("/projects/{pid}/generate")
def generate(pid:str,req:PromptRequest):
    p=get_project(pid)
    if not p.get("adapter_uri"): raise HTTPException(400,"Train the project first")
    return create_job(pid,"generation",{"task":"generate","model":p["base_model"],"adapter_uri":p["adapter_uri"],"prompt":req.prompt,"max_new_tokens":req.max_new_tokens})

@app.get("/jobs/{jid}")
def job(jid:str):
    j=repo.get_job(jid)
    if not j: raise HTTPException(404,"Job not found")
    if j.get("status") in {"completed","failed"}: return j
    try: remote=RunPodClient().status(j["provider_job_id"])
    except Exception as e: return {**j,"provider_status_error":str(e)}
    rs=remote.get("status"); mapped={"IN_QUEUE":"queued","IN_PROGRESS":"running","COMPLETED":"completed","FAILED":"failed","TIMED_OUT":"failed","CANCELLED":"failed"}.get(rs,j["status"])
    fields={"status":mapped,"provider_status":rs}
    if remote.get("output") is not None: fields["result"]=remote["output"]
    if remote.get("error"): fields["error"]=remote["error"]
    repo.update_job(jid,**fields); j={**j,**fields,"updated_at":now_iso()}
    if mapped=="completed" and j["kind"]=="training":
        output=remote.get("output") or {}; adapter_uri=output.get("adapter_uri") or get_project(j["project_id"]).get("pending_adapter_uri")
        repo.update_project(j["project_id"],status="trained",adapter_uri=adapter_uri)
    elif mapped=="failed" and j["kind"]=="training": repo.update_project(j["project_id"],status="training_failed")
    return j
