from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any

from google.cloud import secretmanager
from hubspot import HubSpot
from hubspot.crm.deals import SimplePublicObjectInput

from ..models.opportunity import Opportunity

logger = logging.getLogger(__name__)


class HubSpotIngestor:
    """Ingestor for HubSpot CRM deals."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        project_id: str | None = None,
    ) -> None:
        """Initialize HubSpot ingestor.

        Args:
            api_key: HubSpot API key (or fetch from Secret Manager)
            project_id: GCP project ID for Secret Manager
        """
        # Get API key from Secret Manager if not provided
        if not api_key and project_id:
            api_key = self._get_secret(project_id, "hubspot-api-key")

        self.client = HubSpot(access_token=api_key)

    def get_opportunity(self, deal_id: str) -> Opportunity:
        """Fetch a single opportunity by HubSpot deal ID.

        Args:
            deal_id: HubSpot deal ID

        Returns:
            Opportunity instance
        """
        deal = self.client.crm.deals.basic_api.get_by_id(
            deal_id=deal_id,
            properties=[
                "dealname",
                "company",
                "goal",
                "persona",
                "deadline",
                "budget",
                "must_have_features",
                "references",
                "constraints",
                "has_copy",
                "has_photos",
            ],
        )

        return self._parse_deal(deal)

    def list_opportunities(
        self,
        *,
        pipeline_id: str | None = None,
        stage_id: str | None = None,
        limit: int = 100,
    ) -> list[Opportunity]:
        """List opportunities from HubSpot.

        Args:
            pipeline_id: Filter by pipeline ID
            stage_id: Filter by pipeline stage ID
            limit: Maximum number of results

        Returns:
            List of Opportunity instances
        """
        filter_groups = []

        if pipeline_id:
            filter_groups.append(
                {
                    "filters": [
                        {
                            "propertyName": "pipeline",
                            "operator": "EQ",
                            "value": pipeline_id,
                        }
                    ]
                }
            )

        if stage_id:
            filter_groups.append(
                {
                    "filters": [
                        {
                            "propertyName": "dealstage",
                            "operator": "EQ",
                            "value": stage_id,
                        }
                    ]
                }
            )

        search_request = {
            "filterGroups": filter_groups,
            "properties": [
                "dealname",
                "company",
                "goal",
                "persona",
                "deadline",
                "budget",
                "must_have_features",
                "references",
                "constraints",
                "has_copy",
                "has_photos",
            ],
            "limit": limit,
        }

        results = self.client.crm.deals.search_api.do_search(
            public_object_search_request=search_request
        )

        opportunities = []
        for deal in results.results:
            try:
                opportunities.append(self._parse_deal(deal))
            except Exception as exc:
                logger.warning(
                    f"Failed to parse HubSpot deal {deal.id}: {exc}",
                    exc_info=True,
                )

        logger.info(
            f"Fetched {len(opportunities)} opportunities from HubSpot",
            extra={"pipeline_id": pipeline_id, "stage_id": stage_id},
        )

        return opportunities

    def _parse_deal(self, deal: Any) -> Opportunity:
        """Parse a HubSpot deal into an Opportunity.

        Args:
            deal: HubSpot deal object

        Returns:
            Opportunity instance
        """
        props = deal.properties

        # Parse multi-value fields
        must_have = self._parse_list(props.get("must_have_features", ""))
        references = self._parse_list(props.get("references", ""))
        constraints = self._parse_list(props.get("constraints", ""))

        # Parse date
        deadline = None
        if props.get("deadline"):
            try:
                deadline = datetime.fromisoformat(props["deadline"]).date()
            except Exception:
                pass

        # Parse assets
        assets = {
            "copy": props.get("has_copy", "false").lower() == "true",
            "photo": props.get("has_photos", "false").lower() == "true",
        }

        return Opportunity(
            id=deal.id,
            title=props.get("dealname", ""),
            company=props.get("company", ""),
            goal=props.get("goal", ""),
            persona=props.get("persona"),
            deadline=deadline,
            budget_band=props.get("budget"),
            must_have=must_have,
            references=references,
            constraints=constraints,
            assets=assets,
        )

    def _parse_list(self, value: str) -> list[str]:
        """Parse semicolon-separated list from HubSpot property.

        Args:
            value: Semicolon-separated string

        Returns:
            List of values
        """
        if not value:
            return []
        return [item.strip() for item in value.split(";") if item.strip()]

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


__all__ = ["HubSpotIngestor"]
