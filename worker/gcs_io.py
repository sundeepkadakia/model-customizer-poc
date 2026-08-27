from __future__ import annotations
import os
from pathlib import Path
from google.cloud import storage
from google.oauth2 import service_account
import json


def parse_gs(uri:str):
    if not uri.startswith("gs://"): raise ValueError(f"Expected gs:// URI, got {uri}")
    bucket,_,name=uri[5:].partition("/")
    return bucket,name.rstrip("/")


def client():
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON")

    if not raw:
        raise RuntimeError(
            "GCP_SERVICE_ACCOUNT_JSON is missing from the RunPod worker environment"
        )

    try:
        info = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"GCP_SERVICE_ACCOUNT_JSON is present but invalid JSON: {e}"
        )
    creds = service_account.Credentials.from_service_account_info(info)
    return storage.Client(project=info.get("project_id") or os.getenv("GCP_PROJECT_ID"), credentials=creds,)


def download_file(uri:str,dest:Path):
    b,n=parse_gs(uri); dest.parent.mkdir(parents=True,exist_ok=True); client().bucket(b).blob(n).download_to_filename(dest); return dest


def download_prefix(uri:str,dest:Path):
    b,prefix=parse_gs(uri); c=client(); dest.mkdir(parents=True,exist_ok=True)
    for blob in c.list_blobs(b,prefix=prefix+"/"):
        rel=blob.name[len(prefix)+1:]
        if not rel: continue
        path=dest/rel; path.parent.mkdir(parents=True,exist_ok=True); blob.download_to_filename(path)
    return dest


def upload_dir(src:Path,uri:str):
    b,prefix=parse_gs(uri); bucket=client().bucket(b)
    for path in src.rglob("*"):
        if path.is_file(): bucket.blob(f"{prefix}/{path.relative_to(src).as_posix()}").upload_from_filename(path)
    return uri
