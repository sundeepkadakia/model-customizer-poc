# Model Customizer MVP 0.2

**Product idea:** anyone can improve their AI without learning LoRA, chat templates, or training infrastructure.

This MVP turns flexible business data into a strict internal training format, fine-tunes a LoRA adapter, holds examples out of training, evaluates base vs. tuned behavior, and exposes the tuned adapter through an API endpoint.

## What this version proves

1. Create a project by describing the desired outcome in plain English.
2. Upload `.csv`, `.json`, or `.jsonl` examples.
3. Automatically normalize common schemas into one conversational representation.
4. Split examples deterministically into **80% train / 20% held-out eval**.
5. Train a Qwen LoRA adapter in a background job.
6. Evaluate the adapter on examples it never trained on.
7. Compare base vs. tuned generations on a new prompt.
8. Call a tuned-model generation endpoint.
9. Persist projects and jobs locally in SQLite, so restarting FastAPI does not erase them.

## External formats: flexible

### Prompt + ideal response

CSV is fine:

```csv
customer_message,agent_reply
"I was charged twice","I can help you investigate the duplicate charge..."
```

JSONL is fine:

```json
{"question":"How do I cancel?","answer":"Open Settings > Billing..."}
```

The importer recognizes common prompt aliases such as:

`prompt`, `input`, `question`, `query`, `user_message`, `customer_message`, `ticket`, `instruction`

and response aliases such as:

`response`, `output`, `answer`, `completion`, `ideal_response`, `assistant_response`, `agent_reply`, `best_rep_response`

If automatic detection is wrong, the UI lets the user specify the two column names.

### Conversations

```json
{"messages":[
  {"role":"user","content":"I was charged twice"},
  {"role":"assistant","content":"I can help you investigate that..."}
]}
```

The importer also accepts `conversation`, `chat`, or `turns`, and maps speakers such as `customer`/`human` to `user` and `agent`/`bot` to `assistant`.

## Internal format: strict

Everything becomes:

```json
{
  "messages": [
    {"role":"user","content":"..."},
    {"role":"assistant","content":"..."}
  ],
  "metadata": {"source_row": 1}
}
```

This is intentionally aligned with TRL's conversational dataset support, so the model tokenizer applies the appropriate chat template during training.

## Local setup

The dependency pins below are intentionally compatible with the Intel-Mac environment used for this POC:

- Python 3.12
- PyTorch 2.2.2
- NumPy 1.26.4
- Transformers 4.52.4
- PEFT 0.15.2
- TRL 0.17.0
- Accelerate 1.7.0

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`.

## Sample data

Use either:

```text
sample_data/support_style.csv
sample_data/support_style.jsonl
sample_data/support_conversations.jsonl
```

The CSV is useful for demonstrating that customers do **not** need to know JSONL or ChatML.

## Persistence

The MVP uses standard-library SQLite:

```text
backend/model_customizer.sqlite3
```

It stores project and job metadata. Large artifacts stay on disk:

```text
backend/data/<project-id>/normalized.jsonl
backend/data/<project-id>/train.jsonl
backend/data/<project-id>/eval.jsonl
backend/adapters/<project-id>/adapter_model.safetensors
```

The production migration is straightforward:

```text
SQLite              -> PostgreSQL
local data/adapters  -> S3 / R2 / GCS
local background job -> managed GPU worker / queue
```

## API flow

### Create project

```http
POST /projects
```

```json
{
  "name": "Support Agent",
  "goal": "Respond like our best support representative",
  "base_model": "Qwen/Qwen3-0.6B"
}
```

### Upload and normalize

```http
POST /projects/{project_id}/dataset
Content-Type: multipart/form-data
```

Fields:

- `file`
- `mode`: `auto`, `prompt_response`, or `conversation`
- `prompt_field` optional
- `response_field` optional

### Train

```http
POST /projects/{project_id}/train
```

The request returns immediately with a job ID. Poll:

```http
GET /jobs/{job_id}
```

### Evaluate held-out examples

```http
POST /projects/{project_id}/evaluate
```

Poll the returned job. The current local evaluation reports:

- base held-out reference loss
- tuned held-out reference loss
- relative reference-fit improvement
- base/tuned perplexity
- a rough generated token-overlap F1
- sample base/tuned generations

**Important:** token overlap is not a general quality metric. The primary local MVP metric is held-out reference likelihood. A production product should add customer-specific rubrics and judge/evaluator models.

### Compare on a new prompt

```http
POST /projects/{project_id}/compare
```

```json
{"prompt":"I was charged twice. Can you help?","max_new_tokens":50}
```

### Tuned inference endpoint

```http
POST /projects/{project_id}/generate
```

```json
{"prompt":"I need to change plans","max_new_tokens":80}
```

## Why the evaluation is designed this way

The evaluation rows never enter the training file. For each held-out ideal response, the system measures the causal-LM loss under the base model and under the tuned adapter. If tuned loss is lower, the customized model assigns greater probability to the desired answer pattern on unseen data.

This is useful for validating the pipeline, but it is **not yet the final business metric**. The next product layer should generate a rubric from the user's goal, for example:

- policy adherence
- discovery-question quality
- tone
- structured-output validity
- factual correctness
- escalation behavior

Then evaluation can tell a customer *what* improved, not merely that reference likelihood moved.

## Local-Mac notes

The current training defaults are deliberately conservative:

```text
Qwen/Qwen3-0.6B
LoRA rank 4
q_proj + v_proj
batch size 1
max length 128
gradient checkpointing enabled
float32 on MPS
```

Do not optimize the business around this laptop. It is only the local control plane and smoke-test trainer.

## Next production milestone

After validating this MVP with real example datasets:

1. Move the training/evaluation subprocess behind a cloud GPU worker.
2. Replace SQLite with Postgres.
3. Replace local artifacts with object storage.
4. Add automatic dataset quality checks: duplicates, PII, bad outputs, length outliers.
5. Generate evaluation rubrics from the customer's natural-language goal.
6. Add an LLM judge and deterministic validators where appropriate.
7. Add versioned deployments, rollback, and production feedback ingestion.

That is the bridge from **"fine-tune my model"** to **"make my AI better and prove it."**
