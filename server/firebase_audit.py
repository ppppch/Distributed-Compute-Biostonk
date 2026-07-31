"""Write-only Firestore audit records for inference jobs."""

import os
from typing import Any

import firebase_admin
from firebase_admin import firestore


DEFAULT_PROJECT_ID = "civicgrid-e8b69"


class FirestoreAudit:
    """Records job metadata without adding reads to the inference path."""

    def __init__(self, database: Any) -> None:
        self._jobs = database.collection("inference_jobs")

    @classmethod
    def from_environment(cls) -> "FirestoreAudit | None":
        if os.environ.get("FIRESTORE_AUDIT_ENABLED", "false").lower() != "true":
            return None

        project_id = os.environ.get("FIREBASE_PROJECT_ID", DEFAULT_PROJECT_ID)
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(options={"projectId": project_id})

        return cls(firestore.client())

    def record_started(self, sample_count: int) -> str:
        job = self._jobs.document()
        job.set(
            {
                "sample_count": sample_count,
                "status": "running",
                "started_at": firestore.SERVER_TIMESTAMP,
            }
        )
        return job.id

    def record_completed(self, job_id: str) -> None:
        self._jobs.document(job_id).update(
            {
                "status": "completed",
                "completed_at": firestore.SERVER_TIMESTAMP,
            }
        )