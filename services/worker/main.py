from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auto_proposal_drafter.firestore_job_store import FirestoreJobStore
from auto_proposal_drafter.generator import ProposalGenerator
from auto_proposal_drafter.logging_config import set_trace_id, setup_logging
from auto_proposal_drafter.models.job import JobOutputs, JobStatus
from auto_proposal_drafter.models.opportunity import Opportunity
from auto_proposal_drafter.post_processor import PostProcessor
from auto_proposal_drafter.pubsub_client import PubSubClient

# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
PROJECT_ID = os.getenv("PROJECT_ID", "auto-proposal-drafter")
PUBSUB_TOPIC_COMPLETED = os.getenv("PUBSUB_TOPIC_DRAFT_COMPLETED", "draft-completed")

# Setup logging
setup_logging(environment=ENVIRONMENT, project_id=PROJECT_ID)
logger = logging.getLogger(__name__)

# Initialize services
job_store = FirestoreJobStore(project_id=PROJECT_ID)
pubsub_client = PubSubClient(project_id=PROJECT_ID)
proposal_generator = ProposalGenerator()
post_processor = PostProcessor(project_id=PROJECT_ID)

app = FastAPI(title="Auto Proposal Drafter Worker", version="0.1.0")


class PubSubMessage(BaseModel):
    """Pub/Sub push message format."""

    message: dict[str, Any]
    subscription: str


@app.post("/v1/worker/process")
async def process_draft_request(request: Request) -> JSONResponse:
    """Process a draft generation request from Pub/Sub.

    This endpoint is called by Pub/Sub push subscription.
    """
    # Generate trace ID for request tracking
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    try:
        # Parse Pub/Sub message
        body = await request.json()
        pubsub_message = PubSubMessage.model_validate(body)

        # Decode message data
        message_data = pubsub_message.message.get("data", "")
        if message_data:
            decoded_data = base64.b64decode(message_data).decode("utf-8")
            payload = json.loads(decoded_data)
        else:
            raise HTTPException(status_code=400, detail="No message data")

        job_id = payload.get("job_id")
        source = payload.get("source")
        record_id = payload.get("record_id")

        if not job_id or not source or not record_id:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: job_id, source, record_id",
            )

        logger.info(
            "Processing draft request",
            extra={
                "job_id": job_id,
                "source": source,
                "record_id": record_id,
                "trace_id": trace_id,
            },
        )

        # Process the job
        await _process_job(job_id, source, record_id)

        return JSONResponse({"status": "success", "job_id": job_id})

    except Exception as exc:
        logger.error(
            "Failed to process draft request",
            exc_info=True,
            extra={"trace_id": trace_id, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail=str(exc))


async def _process_job(job_id: str, source: str, record_id: str) -> None:
    """Process a single draft generation job.

    Args:
        job_id: Job ID
        source: Source system (notion, hubspot, manual)
        record_id: Record ID in source system
    """
    try:
        # Update job to in_progress
        job_store.update_job(job_id, status=JobStatus.in_progress, progress=0.1)

        # Load opportunity from source
        # TODO: Implement actual repository based on source
        opportunity = await _load_opportunity(source, record_id)

        logger.info(
            "Loaded opportunity",
            extra={
                "job_id": job_id,
                "opportunity_id": opportunity.id,
                "company": opportunity.company,
            },
        )

        # Update progress
        job_store.update_job(job_id, progress=0.3)

        # Generate draft bundle
        bundle = await asyncio.to_thread(proposal_generator.generate, opportunity)

        logger.info(
            "Generated draft bundle",
            extra={
                "job_id": job_id,
                "sections_count": sum(
                    len(page.sections) for page in bundle.structure.site_map
                ),
                "line_items_count": len(bundle.estimate.line_items),
            },
        )

        # Update progress
        job_store.update_job(job_id, progress=0.8)

        # Prepare outputs
        bundle_dict = bundle.model_dump()
        outputs = JobOutputs(
            structure=bundle_dict["structure"],
            wire=bundle_dict["wire"],
            estimate=bundle_dict["estimate"],
            summary=bundle_dict["summary"],
        )

        # Update job to completed
        job_store.update_job(
            job_id, status=JobStatus.completed, progress=1.0, outputs=outputs
        )

        # Post-process: generate Figma feed and other outputs
        try:
            post_outputs = post_processor.process_draft(
                job_id=job_id,
                record_id=record_id,
                structure=bundle.structure,
                wire=bundle.wire,
                estimate=bundle.estimate,
                summary=bundle.summary_markdown,
                options={},
            )
            logger.info(
                "Post-processing completed",
                extra={"job_id": job_id, "outputs": post_outputs},
            )
        except Exception as post_exc:
            logger.warning(
                "Post-processing failed (non-fatal)",
                exc_info=True,
                extra={"job_id": job_id, "error": str(post_exc)},
            )

        # Publish completion event
        pubsub_client.publish_draft_completed(
            job_id=job_id,
            record_id=record_id,
            outputs=bundle_dict,
        )

        logger.info("Draft generation completed", extra={"job_id": job_id})

    except Exception as exc:
        logger.error(
            "Draft generation failed",
            exc_info=True,
            extra={"job_id": job_id, "error": str(exc)},
        )

        # Update job to failed
        job_store.update_job(
            job_id,
            status=JobStatus.failed,
            progress=1.0,
            errors=[str(exc)],
        )

        raise


async def _load_opportunity(source: str, record_id: str) -> Opportunity:
    """Load opportunity from source system.

    TODO: Implement actual repository based on source (Notion, HubSpot, etc.)

    Args:
        source: Source system identifier
        record_id: Record ID in source system

    Returns:
        Opportunity instance
    """
    # For now, return a mock opportunity
    # This should be replaced with actual repository implementation
    from pathlib import Path

    fixture_path = Path("data/opportunities") / f"{record_id}.json"
    if fixture_path.exists():
        return Opportunity.model_validate_json(
            fixture_path.read_text(encoding="utf-8")
        )

    # Return a minimal opportunity for testing
    from datetime import date, timedelta

    return Opportunity(
        id=record_id,
        title="Sample Opportunity",
        company="Sample Company",
        goal="リード獲得",
        persona="企業の経営者",
        deadline=date.today() + timedelta(days=60),
        budget_band="200-300万円",
        must_have=["高いCVR", "直感的な導線"],
        references=["企業A", "企業B"],
        constraints=["短納期"],
        assets={"copy": False, "photo": False},
    )


@app.get("/health")
async def healthcheck() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})
