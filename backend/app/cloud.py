from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from google.cloud import firestore, storage


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FirestoreRepo:
    def __init__(self):
        self.db = firestore.Client(project=os.getenv("GCP_PROJECT_ID") or None)

    def create_project(self, project: dict) -> dict:
        self.db.collection("projects").document(project["id"]).set(project)
        return project

    def get_project(self, project_id: str) -> dict | None:
        snap = self.db.collection("projects").document(project_id).get()
        return snap.to_dict() if snap.exists else None

    def list_projects(self) -> list[dict]:
        docs = self.db.collection("projects").order_by("created_at", direction=firestore.Query.DESCENDING).stream()
        return [d.to_dict() for d in docs]

    def update_project(self, project_id: str, **fields: Any) -> None:
        fields["updated_at"] = now_iso()
        self.db.collection("projects").document(project_id).update(fields)

    def create_job(self, job: dict) -> dict:
        self.db.collection("jobs").document(job["id"]).set(job)
        return job

    def get_job(self, job_id: str) -> dict | None:
        snap = self.db.collection("jobs").document(job_id).get()
        return snap.to_dict() if snap.exists else None

    def update_job(self, job_id: str, **fields: Any) -> None:
        fields["updated_at"] = now_iso()
        self.db.collection("jobs").document(job_id).update(fields)


class GCSStore:
    def __init__(self):
        self.bucket_name = os.environ["GCS_BUCKET"]
        self.client = storage.Client(project=os.getenv("GCP_PROJECT_ID") or None)
        self.bucket = self.client.bucket(self.bucket_name)

    def uri(self, object_name: str) -> str:
        return f"gs://{self.bucket_name}/{object_name}"

    def upload_bytes(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        blob = self.bucket.blob(object_name)
        blob.upload_from_string(data, content_type=content_type)
        return self.uri(object_name)

    def upload_text(self, object_name: str, text: str, content_type: str = "application/json") -> str:
        return self.upload_bytes(object_name, text.encode("utf-8"), content_type)


class RunPodClient:
    def __init__(self):
        self.api_key = os.environ["RUNPOD_API_KEY"]
        self.endpoint_id = os.environ["RUNPOD_ENDPOINT_ID"]
        self.base = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        self.headers = {"authorization": f"Bearer {self.api_key}", "content-type": "application/json"}

    def run_async(self, payload: dict, execution_timeout_ms: int = 3_600_000) -> dict:
        body = {
            "input": payload,
            "policy": {"executionTimeout": execution_timeout_ms, "ttl": execution_timeout_ms + 3_600_000},
        }
        with httpx.Client(timeout=30) as client:
            r = client.post(f"{self.base}/run", headers=self.headers, json=body)
            r.raise_for_status()
            return r.json()

    def status(self, provider_job_id: str) -> dict:
        with httpx.Client(timeout=30) as client:
            r = client.get(f"{self.base}/status/{provider_job_id}", headers=self.headers)
            r.raise_for_status()
            return r.json()
