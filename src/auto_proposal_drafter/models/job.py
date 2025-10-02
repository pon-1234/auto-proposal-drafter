from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "QUEUED"
    in_progress = "IN_PROGRESS"
    completed = "COMPLETED"
    failed = "FAILED"


class JobOutputs(BaseModel):
    notion_url: str | None = None
    figma_wire_json_url: str | None = None
    sheets_url: str | None = None
    asana_task_url: str | None = None
    structure: Mapping[str, Any] | None = None
    wire: Mapping[str, Any] | None = None
    estimate: Mapping[str, Any] | None = None
    summary: str | None = None


class JobRecord(BaseModel):
    id: str
    status: JobStatus
    progress: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source: str | None = None
    record_id: str | None = None
    priority: str | None = None
    errors: Sequence[str] = Field(default_factory=list)
    outputs: JobOutputs = Field(default_factory=JobOutputs)


__all__ = ["JobRecord", "JobStatus", "JobOutputs"]
