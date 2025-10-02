from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any

from google.cloud import secretmanager
from notion_client import Client

from ..models.opportunity import Opportunity

logger = logging.getLogger(__name__)


class NotionIngestor:
    """Ingestor for Notion database opportunities."""

    def __init__(
        self,
        *,
        database_id: str,
        api_key: str | None = None,
        project_id: str | None = None,
    ) -> None:
        """Initialize Notion ingestor.

        Args:
            database_id: Notion database ID
            api_key: Notion API key (or fetch from Secret Manager)
            project_id: GCP project ID for Secret Manager
        """
        self.database_id = database_id

        # Get API key from Secret Manager if not provided
        if not api_key and project_id:
            api_key = self._get_secret(project_id, "notion-api-key")

        self.client = Client(auth=api_key)

    def get_opportunity(self, page_id: str) -> Opportunity:
        """Fetch a single opportunity by Notion page ID.

        Args:
            page_id: Notion page ID

        Returns:
            Opportunity instance
        """
        page = self.client.pages.retrieve(page_id=page_id)
        return self._parse_page(page)

    def list_opportunities(
        self,
        *,
        status_filter: str | None = None,
        limit: int = 100,
    ) -> list[Opportunity]:
        """List opportunities from Notion database.

        Args:
            status_filter: Filter by status property (e.g., "新規", "対応中")
            limit: Maximum number of results

        Returns:
            List of Opportunity instances
        """
        query_params: dict[str, Any] = {"database_id": self.database_id}

        if status_filter:
            query_params["filter"] = {
                "property": "ステータス",
                "select": {"equals": status_filter},
            }

        query_params["page_size"] = min(limit, 100)

        results = self.client.databases.query(**query_params)

        opportunities = []
        for page in results.get("results", []):
            try:
                opportunities.append(self._parse_page(page))
            except Exception as exc:
                logger.warning(
                    f"Failed to parse Notion page {page.get('id')}: {exc}",
                    exc_info=True,
                )

        logger.info(
            f"Fetched {len(opportunities)} opportunities from Notion",
            extra={"database_id": self.database_id},
        )

        return opportunities

    def _parse_page(self, page: dict[str, Any]) -> Opportunity:
        """Parse a Notion page into an Opportunity.

        Args:
            page: Notion page object

        Returns:
            Opportunity instance
        """
        props = page.get("properties", {})

        # Extract fields from Notion properties
        # Adjust property names based on your actual Notion database schema
        opportunity_id = self._get_rich_text(props.get("ID", {}))
        title = self._get_title(props.get("案件名", {}))
        company = self._get_rich_text(props.get("会社名", {}))
        goal = self._get_rich_text(props.get("目的", {}))
        persona = self._get_rich_text(props.get("ペルソナ", {}))
        deadline = self._get_date(props.get("納期", {}))
        budget_band = self._get_rich_text(props.get("予算感", {}))
        must_have = self._get_multi_select(props.get("必須要件", {}))
        references = self._get_multi_select(props.get("参考事例", {}))
        constraints = self._get_multi_select(props.get("制約条件", {}))

        # Parse assets (copy/photo availability)
        assets = {
            "copy": self._get_checkbox(props.get("コピー提供", {})),
            "photo": self._get_checkbox(props.get("写真素材提供", {})),
        }

        return Opportunity(
            id=opportunity_id or page["id"],
            title=title,
            company=company,
            goal=goal,
            persona=persona,
            deadline=deadline,
            budget_band=budget_band,
            must_have=must_have,
            references=references,
            constraints=constraints,
            assets=assets,
        )

    def _get_title(self, prop: dict[str, Any]) -> str:
        """Extract title from Notion property."""
        titles = prop.get("title", [])
        return titles[0].get("plain_text", "") if titles else ""

    def _get_rich_text(self, prop: dict[str, Any]) -> str:
        """Extract rich text from Notion property."""
        texts = prop.get("rich_text", [])
        return texts[0].get("plain_text", "") if texts else ""

    def _get_date(self, prop: dict[str, Any]) -> date | None:
        """Extract date from Notion property."""
        date_obj = prop.get("date")
        if not date_obj:
            return None

        date_str = date_obj.get("start")
        if not date_str:
            return None

        # Parse ISO date
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except Exception:
            return None

    def _get_multi_select(self, prop: dict[str, Any]) -> list[str]:
        """Extract multi-select values from Notion property."""
        options = prop.get("multi_select", [])
        return [opt.get("name", "") for opt in options]

    def _get_checkbox(self, prop: dict[str, Any]) -> bool:
        """Extract checkbox value from Notion property."""
        return prop.get("checkbox", False)

    def _get_secret(self, project_id: str, secret_id: str) -> str:
        """Fetch secret from Secret Manager.

        Args:
            project_id: GCP project ID
            secret_id: Secret ID

        Returns:
            Secret value
        """
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")


__all__ = ["NotionIngestor"]
