from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models.opportunity import Opportunity


class OpportunityRepository(Protocol):
    def get(self, *, source: str, record_id: str) -> Opportunity:
        ...


class LocalOpportunityRepository:
    def __init__(self, *, base_path: Path) -> None:
        self._base_path = base_path

    def get(self, *, source: str, record_id: str) -> Opportunity:
        file_path = self._base_path / f"{record_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Opportunity payload not found: {file_path}")
        with file_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        return Opportunity.model_validate(data)


__all__ = ["OpportunityRepository", "LocalOpportunityRepository"]
