from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import runpod
from gcs_io import download_file, download_prefix, upload_dir

ROOT=Path(__file__).resolve().parent

WORKER_VERSION = "v0.4-thinking-off"

def run(cmd:list[str]):
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode!=0: raise RuntimeError((p.stdout+"\n"+p.stderr)[-12000:])
    lines=[x for x in p.stdout.splitlines() if x.strip()]
    return p.stdout, (json.loads(lines[-1]) if lines and lines[-1].lstrip().startswith("{") else None)


def handler(job):
    print("=== handler started ===", flush=True)
    print("WORKER_VERSION:", WORKER_VERSION, flush=True)
    x=job["input"]; task=x["task"]
    print("task:", task, flush=True)
    print("GCP_PROJECT_ID:", os.getenv("GCP_PROJECT_ID"), flush=True)

    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    print("GCP_SERVICE_ACCOUNT_JSON present:", bool(raw), flush=True)

    if raw:
        print("GCP_SERVICE_ACCOUNT_JSON length:", len(raw), flush=True)
        print("GCP_SERVICE_ACCOUNT_JSON startswith {:", raw.lstrip().startswith("{"), flush=True)
    
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        if task=="train":
            print("dataset_uri:", x["dataset_uri"], flush=True)
            print("adapter_uri:", x["adapter_uri"], flush=True)
            dataset=download_file(x["dataset_uri"],td/"train.jsonl"); out=td/"adapter"
            print("dataset downloaded:", dataset, flush=True)
            cmd=[sys.executable,str(ROOT/"training"/"train_lora.py"),"--model",x["model"],"--dataset",str(dataset),"--output",str(out),"--epochs",str(x.get("epochs",1)),"--lr",str(x.get("learning_rate",2e-4)),"--rank",str(x.get("lora_rank",8)),"--max-length",str(x.get("max_length",512))]
            stdout,_=run(cmd); upload_dir(out,x["adapter_uri"]); return {"ok":True,"adapter_uri":x["adapter_uri"],"log_tail":stdout[-4000:]}
        adapter=download_prefix(x["adapter_uri"],td/"adapter")
        if task=="evaluate":
            dataset=download_file(x["dataset_uri"],td/"eval.jsonl"); _,result=run([sys.executable,str(ROOT/"training"/"evaluate.py"),"--model",x["model"],"--adapter",str(adapter),"--dataset",str(dataset),"--max-new-tokens",str(x.get("max_new_tokens",50))]); return result
        script="compare.py" if task=="compare" else "generate.py"
        _,result=run([sys.executable,str(ROOT/"training"/script),"--model",x["model"],"--adapter",str(adapter),"--prompt",x["prompt"],"--max-new-tokens",str(x.get("max_new_tokens",100))]); return result

runpod.serverless.start({"handler":handler})
