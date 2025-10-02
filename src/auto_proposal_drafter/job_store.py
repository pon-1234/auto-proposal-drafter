from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Dict

from .models.job import JobOutputs, JobRecord, JobStatus


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create_job(self, *, source: str, record_id: str | None, priority: str | None) -> JobRecord:
        with self._lock:
            job_id = self._generate_id(record_id)
            job = JobRecord(
                id=job_id,
                status=JobStatus.queued,
                source=source,
                record_id=record_id,
                priority=priority,
            )
            self._jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: float | None = None,
        outputs: JobOutputs | None = None,
        errors: list[str] | None = None,
    ) -> JobRecord:
        with self._lock:
            job = self._jobs[job_id]
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if outputs is not None:
                job.outputs = outputs
            if errors is not None:
                job.errors = list(errors)
            job.updated_at = datetime.utcnow()
            self._jobs[job_id] = job
            return job

    def _generate_id(self, record_id: str | None) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        if record_id:
            safe = record_id.replace("/", "-")
            return f"job_{safe}_{suffix}"
        return f"job_{ts}_{suffix}"


__all__ = ["JobStore"]
