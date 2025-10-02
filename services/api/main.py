from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from auto_proposal_drafter.firestore_job_store import FirestoreJobStore
from auto_proposal_drafter.generator import ProposalGenerator
from auto_proposal_drafter.job_store import JobStore
from auto_proposal_drafter.logging_config import setup_logging
from auto_proposal_drafter.models.job import JobOutputs, JobRecord, JobStatus
from auto_proposal_drafter.models.opportunity import Opportunity
from auto_proposal_drafter.opportunity_repository import LocalOpportunityRepository
from auto_proposal_drafter.post_processor import PostProcessor
from auto_proposal_drafter.pubsub_client import PubSubClient


class GenerateDraftRequest(BaseModel):
    source: str = Field(default="manual")
    record_id: str
    priority: str | None = None
    callback_url: str | None = None
    payload: Opportunity | None = Field(default=None, description="Optional inline Opportunity payload")


class GenerateDraftResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    progress: float
    outputs: JobOutputs
    errors: list[str]

    @staticmethod
    def from_record(record: JobRecord) -> "JobResponse":
        return JobResponse(
            id=record.id,
            status=record.status,
            progress=record.progress,
            outputs=record.outputs,
            errors=list(record.errors),
        )


# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
PROJECT_ID = os.getenv("PROJECT_ID")
PUBSUB_TOPIC_DRAFT_REQUESTS = os.getenv("PUBSUB_TOPIC_DRAFT_REQUESTS", "draft-requests")

# Setup logging
setup_logging(environment=ENVIRONMENT, project_id=PROJECT_ID)

app = FastAPI(title="Auto Proposal Drafter API", version="0.1.0")

# Use Firestore in production, in-memory for dev
if ENVIRONMENT == "dev":
    job_store = JobStore()
else:
    job_store = FirestoreJobStore(project_id=PROJECT_ID)

# Initialize Pub/Sub client for production
pubsub_client = PubSubClient(project_id=PROJECT_ID) if PROJECT_ID else None

# Initialize post processor for dev mode
post_processor = PostProcessor(project_id=PROJECT_ID) if PROJECT_ID and ENVIRONMENT == "dev" else None

proposal_generator = ProposalGenerator()
repo_base_path = Path("data/opportunities").resolve()
repository = LocalOpportunityRepository(base_path=repo_base_path)


@app.post("/v1/drafts:generate", response_model=GenerateDraftResponse)
async def generate_draft(request: GenerateDraftRequest, background_tasks: BackgroundTasks) -> GenerateDraftResponse:
    job = job_store.create_job(source=request.source, record_id=request.record_id, priority=request.priority)

    # In production, publish to Pub/Sub; in dev, use background task
    if pubsub_client and ENVIRONMENT != "dev":
        pubsub_client.publish_draft_request(
            source=request.source,
            record_id=request.record_id,
            job_id=job.id,
            priority=request.priority,
        )
    else:
        background_tasks.add_task(_run_job, job.id, request)

    return GenerateDraftResponse(job_id=job.id, status=job.status)


@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    record = job_store.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_record(record)


async def _run_job(job_id: str, request: GenerateDraftRequest) -> None:
    job_store.update_job(job_id, status=JobStatus.in_progress, progress=0.1)
    try:
        opportunity = request.payload or repository.get(source=request.source, record_id=request.record_id)
        bundle = await asyncio.to_thread(proposal_generator.generate, opportunity)
        bundle_dict = bundle.model_dump()
        outputs = JobOutputs(
            structure=bundle_dict["structure"],
            wire=bundle_dict["wire"],
            estimate=bundle_dict["estimate"],
            summary=bundle_dict["summary"],
        )
        job_store.update_job(job_id, status=JobStatus.completed, progress=1.0, outputs=outputs)

        # Post-process in dev mode
        if post_processor:
            try:
                post_outputs = await asyncio.to_thread(
                    post_processor.process_draft,
                    job_id=job_id,
                    record_id=request.record_id,
                    structure=bundle.structure,
                    wire=bundle.wire,
                    estimate=bundle.estimate,
                    summary=bundle.summary_markdown,
                    options={},
                )
            except Exception as post_exc:
                pass  # Non-fatal, already logged

    except Exception as exc:  # pragma: no cover - safety net
        job_store.update_job(job_id, status=JobStatus.failed, progress=1.0, errors=[str(exc)])


@app.get("/health")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok"})
