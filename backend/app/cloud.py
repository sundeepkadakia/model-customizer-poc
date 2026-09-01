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

    def list_memberships(self, user_id: str) -> list[dict]:
        docs = self.db.collection("memberships").where("user_id", "==", user_id).where("status", "==", "active").stream()
        return [d.to_dict() for d in docs]

    def get_membership(self, organization_id: str, user_id: str) -> dict | None:
        snap = self.db.collection("memberships").document(f"{organization_id}_{user_id}").get()
        membership = snap.to_dict() if snap.exists else None
        return membership if membership and membership.get("status") == "active" else None

    def get_organization(self, organization_id: str) -> dict | None:
        snap = self.db.collection("organizations").document(organization_id).get()
        return snap.to_dict() if snap.exists else None

    def list_projects(self, organization_ids: list[str]) -> list[dict]:
        if not organization_ids:
            return []
        projects: list[dict] = []
        for start in range(0, len(organization_ids), 30):
            chunk = organization_ids[start:start + 30]
            docs = self.db.collection("projects").where("organization_id", "in", chunk).stream()
            projects.extend(d.to_dict() for d in docs)
        return sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)

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
