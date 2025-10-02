from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import asana
import gspread
from google.auth import default
from google.cloud import secretmanager
from notion_client import Client

from .models.estimate import EstimateDraft
from .models.structure import StructureDraft
from .models.wire import WireDraft

logger = logging.getLogger(__name__)


class PostProcessor:
    """Post-processing service for distributing draft outputs."""

    def __init__(
        self,
        *,
        project_id: str,
        notion_api_key: str | None = None,
        asana_access_token: str | None = None,
    ) -> None:
        """Initialize post processor.

        Args:
            project_id: GCP project ID
            notion_api_key: Notion API key (or fetch from Secret Manager)
            asana_access_token: Asana access token (or fetch from Secret Manager)
        """
        self.project_id = project_id

        # Get secrets from Secret Manager if not provided
        if not notion_api_key:
            notion_api_key = self._get_secret("notion-api-key")

        if not asana_access_token:
            asana_access_token = self._get_secret("asana-access-token")

        self.notion_client = Client(auth=notion_api_key) if notion_api_key else None
        self.asana_client = (
            asana.Client.access_token(asana_access_token)
            if asana_access_token
            else None
        )

        # Initialize Google Sheets client
        credentials, _ = default()
        self.sheets_client = gspread.authorize(credentials)

    def process_draft(
        self,
        *,
        job_id: str,
        record_id: str,
        structure: StructureDraft,
        wire: WireDraft,
        estimate: EstimateDraft,
        summary: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Process and distribute draft outputs.

        Args:
            job_id: Job ID
            record_id: Original record ID
            structure: Structure draft
            wire: Wire draft
            estimate: Estimate draft
            summary: Summary markdown
            options: Optional configuration (Notion page ID, Sheets URL, etc.)

        Returns:
            Dictionary of output URLs
        """
        options = options or {}
        outputs = {}

        try:
            # Update Notion page if configured
            if self.notion_client and options.get("notion_page_id"):
                notion_url = self._update_notion_page(
                    page_id=options["notion_page_id"],
                    structure=structure,
                    estimate=estimate,
                    summary=summary,
                )
                outputs["notion_url"] = notion_url
                logger.info(f"Updated Notion page: {notion_url}")

            # Create/update Google Sheets if configured
            if options.get("sheets_template_id"):
                sheets_url = self._create_estimate_sheet(
                    template_id=options["sheets_template_id"],
                    job_id=job_id,
                    estimate=estimate,
                )
                outputs["sheets_url"] = sheets_url
                logger.info(f"Created estimate sheet: {sheets_url}")

            # Generate Figma plugin feed (signed URL or Cloud Storage)
            figma_url = self._generate_figma_feed(
                job_id=job_id,
                wire=wire,
            )
            outputs["figma_url"] = figma_url
            logger.info(f"Generated Figma feed: {figma_url}")

            # Create Asana task if configured
            if self.asana_client and options.get("asana_project_gid"):
                asana_url = self._create_asana_task(
                    project_gid=options["asana_project_gid"],
                    job_id=job_id,
                    record_id=record_id,
                    summary=summary,
                    outputs=outputs,
                )
                outputs["asana_url"] = asana_url
                logger.info(f"Created Asana task: {asana_url}")

        except Exception as exc:
            logger.error(
                "Failed to process draft outputs",
                exc_info=True,
                extra={"job_id": job_id, "error": str(exc)},
            )
            # Don't raise - partial success is acceptable
            outputs["error"] = str(exc)

        return outputs

    def _update_notion_page(
        self,
        *,
        page_id: str,
        structure: StructureDraft,
        estimate: EstimateDraft,
        summary: str,
    ) -> str:
        """Update Notion page with draft results.

        Args:
            page_id: Notion page ID
            structure: Structure draft
            estimate: Estimate draft
            summary: Summary markdown

        Returns:
            Notion page URL
        """
        # Calculate total estimate
        total_base = sum(item.cost for item in estimate.line_items)
        total = total_base
        for coeff in estimate.coefficients:
            total *= coeff.multiplier

        # Update page properties
        self.notion_client.pages.update(
            page_id=page_id,
            properties={
                "見積金額": {"number": int(total)},
                "ステータス": {"select": {"name": "提案済み"}},
                "提案日": {"date": {"start": datetime.utcnow().isoformat()}},
            },
        )

        # Add summary as page content
        self.notion_client.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "提案サマリ"}}]
                    },
                },
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": summary}}],
                        "language": "markdown",
                    },
                },
            ],
        )

        return f"https://notion.so/{page_id.replace('-', '')}"

    def _create_estimate_sheet(
        self,
        *,
        template_id: str,
        job_id: str,
        estimate: EstimateDraft,
    ) -> str:
        """Create estimate Google Sheet from template.

        Args:
            template_id: Template spreadsheet ID
            job_id: Job ID
            estimate: Estimate draft

        Returns:
            Google Sheets URL
        """
        # Copy template
        template = self.sheets_client.open_by_key(template_id)
        new_sheet = template.copy(title=f"見積_{job_id}")

        # Get first worksheet
        worksheet = new_sheet.sheet1

        # Write line items starting from row 3 (assuming template has header)
        row = 3
        for item in estimate.line_items:
            worksheet.update(
                f"A{row}:E{row}",
                [[item.item, item.qty, item.hours, item.rate, item.cost]],
            )
            row += 1

        # Calculate totals
        total_base = sum(item.cost for item in estimate.line_items)
        total = total_base

        # Write coefficients
        row += 2
        for coeff in estimate.coefficients:
            worksheet.update(
                f"A{row}:C{row}",
                [[coeff.name, f"×{coeff.multiplier:.2f}", coeff.reason]],
            )
            total *= coeff.multiplier
            row += 1

        # Write final total
        row += 1
        worksheet.update(f"A{row}:B{row}", [["最終見積", f"¥{int(total):,}"]])

        return new_sheet.url

    def _generate_figma_feed(
        self,
        *,
        job_id: str,
        wire: WireDraft,
    ) -> str:
        """Generate Figma plugin feed JSON.

        Args:
            job_id: Job ID
            wire: Wire draft

        Returns:
            Feed URL (Cloud Storage signed URL)
        """
        from google.cloud import storage

        feed_json = wire.model_dump()

        # Upload to Cloud Storage
        storage_client = storage.Client(project=self.project_id)
        bucket = storage_client.bucket(f"{self.project_id}-figma-feeds")
        blob = bucket.blob(f"{job_id}/wire.json")
        blob.upload_from_string(
            json.dumps(feed_json, ensure_ascii=False, indent=2),
            content_type="application/json"
        )

        # Generate signed URL valid for 7 days
        url = blob.generate_signed_url(expiration=timedelta(days=7))

        logger.info(f"Generated Figma feed: {url}")

        return url

    def _create_asana_task(
        self,
        *,
        project_gid: str,
        job_id: str,
        record_id: str,
        summary: str,
        outputs: dict[str, str],
    ) -> str:
        """Create Asana task for draft review.

        Args:
            project_gid: Asana project GID
            job_id: Job ID
            record_id: Original record ID
            summary: Summary markdown
            outputs: Output URLs

        Returns:
            Asana task URL
        """
        # Build task notes with output links
        notes_parts = [summary, "\n\n## アウトプット"]
        for key, url in outputs.items():
            if key != "error":
                notes_parts.append(f"- {key}: {url}")

        notes = "\n".join(notes_parts)

        # Create task
        result = self.asana_client.tasks.create(
            {
                "projects": [project_gid],
                "name": f"提案レビュー: {record_id}",
                "notes": notes,
                "due_on": (datetime.utcnow().date() + timedelta(days=3)).isoformat(),
            }
        )

        task_gid = result["gid"]
        task_url = f"https://app.asana.com/0/{project_gid}/{task_gid}"

        return task_url

    def _get_secret(self, secret_id: str) -> str | None:
        """Fetch secret from Secret Manager.

        Args:
            secret_id: Secret ID

        Returns:
            Secret value or None if not found
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(name=name)
            return response.payload.data.decode("UTF-8")
        except Exception as exc:
            logger.warning(
                f"Failed to fetch secret {secret_id}: {exc}",
                exc_info=True,
            )
            return None


# Missing import
from datetime import timedelta

__all__ = ["PostProcessor"]
