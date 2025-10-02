from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .models.job import JobOutputs, JobRecord, JobStatus

logger = logging.getLogger(__name__)


class FirestoreJobStore:
    """Firestore-backed job store for production use."""

    COLLECTION_NAME = "jobs"

    def __init__(self, project_id: str | None = None) -> None:
        self._db = firestore.Client(project=project_id)
        self._collection = self._db.collection(self.COLLECTION_NAME)

    def create_job(
        self, *, source: str, record_id: str | None, priority: str | None
    ) -> JobRecord:
        """Create a new job record in Firestore."""
        job_id = self._generate_id(record_id)
        now = datetime.utcnow()

        job = JobRecord(
            id=job_id,
            status=JobStatus.queued,
            source=source,
            record_id=record_id,
            priority=priority,
            created_at=now,
            updated_at=now,
        )

        doc_ref = self._collection.document(job_id)
        doc_ref.set(self._to_firestore_dict(job))

        logger.info(
            "Created job",
            extra={
                "job_id": job_id,
                "source": source,
                "record_id": record_id,
                "priority": priority,
            },
        )

        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        """Retrieve a job by ID from Firestore."""
        doc_ref = self._collection.document(job_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        return self._from_firestore_dict(doc.id, doc.to_dict())

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: float | None = None,
        outputs: JobOutputs | None = None,
        errors: list[str] | None = None,
    ) -> JobRecord:
        """Update job fields in Firestore."""
        doc_ref = self._collection.document(job_id)

        update_data: dict = {"updated_at": datetime.utcnow()}

        if status is not None:
            update_data["status"] = status.value

        if progress is not None:
            update_data["progress"] = progress

        if outputs is not None:
            update_data["outputs"] = outputs.model_dump()

        if errors is not None:
            update_data["errors"] = errors

        doc_ref.update(update_data)

        logger.info(
            "Updated job",
            extra={
                "job_id": job_id,
                "status": status.value if status else None,
                "progress": progress,
            },
        )

        # Fetch and return updated job
        updated_doc = doc_ref.get()
        return self._from_firestore_dict(updated_doc.id, updated_doc.to_dict())

    def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        source: str | None = None,
        limit: int = 100,
    ) -> list[JobRecord]:
        """List jobs with optional filtering."""
        query = self._collection

        if status is not None:
            query = query.where(filter=FieldFilter("status", "==", status.value))

        if source is not None:
            query = query.where(filter=FieldFilter("source", "==", source))

        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(
            limit
        )

        docs = query.stream()

        return [self._from_firestore_dict(doc.id, doc.to_dict()) for doc in docs]

    def _generate_id(self, record_id: str | None) -> str:
        """Generate a unique job ID."""
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        # Use Firestore auto-generated ID for uniqueness
        doc_ref = self._collection.document()
        suffix = doc_ref.id[:6]

        if record_id:
            safe = record_id.replace("/", "-")
            return f"job_{safe}_{suffix}"
        return f"job_{ts}_{suffix}"

    def _to_firestore_dict(self, job: JobRecord) -> dict:
        """Convert JobRecord to Firestore document dict."""
        data = {
            "status": job.status.value,
            "source": job.source,
            "record_id": job.record_id,
            "priority": job.priority,
            "progress": job.progress,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "errors": job.errors,
        }

        if job.outputs:
            data["outputs"] = job.outputs.model_dump()

        return data

    def _from_firestore_dict(self, job_id: str, data: dict) -> JobRecord:
        """Convert Firestore document dict to JobRecord."""
        outputs = None
        if "outputs" in data and data["outputs"]:
            outputs = JobOutputs.model_validate(data["outputs"])

        return JobRecord(
            id=job_id,
            status=JobStatus(data["status"]),
            source=data["source"],
            record_id=data.get("record_id"),
            priority=data.get("priority"),
            progress=data.get("progress", 0.0),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            outputs=outputs,
            errors=data.get("errors", []),
        )


__all__ = ["FirestoreJobStore"]
