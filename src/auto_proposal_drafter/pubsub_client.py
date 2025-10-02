from __future__ import annotations

import json
import logging
from typing import Any

from google.cloud import pubsub_v1

logger = logging.getLogger(__name__)


class PubSubClient:
    """Wrapper for Google Cloud Pub/Sub operations."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.publisher = pubsub_v1.PublisherClient()

    def publish(
        self,
        topic_id: str,
        message: dict[str, Any],
        *,
        attributes: dict[str, str] | None = None,
    ) -> str:
        """Publish a message to a Pub/Sub topic.

        Args:
            topic_id: The topic ID (e.g., "draft-requests")
            message: The message payload as a dictionary
            attributes: Optional message attributes

        Returns:
            Message ID from Pub/Sub
        """
        topic_path = self.publisher.topic_path(self.project_id, topic_id)

        # Serialize message to JSON bytes
        data = json.dumps(message).encode("utf-8")

        # Publish with optional attributes
        future = self.publisher.publish(
            topic_path, data, **(attributes or {})
        )

        message_id = future.result()

        logger.info(
            "Published message to Pub/Sub",
            extra={
                "topic_id": topic_id,
                "message_id": message_id,
                "attributes": attributes,
            },
        )

        return message_id

    def publish_draft_request(
        self,
        *,
        source: str,
        record_id: str,
        job_id: str,
        priority: str | None = None,
    ) -> str:
        """Publish a draft generation request.

        Args:
            source: Source system (e.g., "notion", "hubspot", "manual")
            record_id: Record ID in the source system
            job_id: Job ID for tracking
            priority: Optional priority level

        Returns:
            Message ID from Pub/Sub
        """
        message = {
            "job_id": job_id,
            "source": source,
            "record_id": record_id,
            "priority": priority,
        }

        attributes = {
            "source": source,
            "job_id": job_id,
        }

        if priority:
            attributes["priority"] = priority

        return self.publish("draft-requests", message, attributes=attributes)

    def publish_draft_completed(
        self,
        *,
        job_id: str,
        record_id: str,
        outputs: dict[str, Any],
    ) -> str:
        """Publish a draft completion notification.

        Args:
            job_id: Job ID
            record_id: Original record ID
            outputs: Draft outputs (structure, wire, estimate, summary)

        Returns:
            Message ID from Pub/Sub
        """
        message = {
            "job_id": job_id,
            "record_id": record_id,
            "outputs": outputs,
        }

        attributes = {
            "job_id": job_id,
            "event_type": "draft_completed",
        }

        return self.publish("draft-completed", message, attributes=attributes)


__all__ = ["PubSubClient"]
