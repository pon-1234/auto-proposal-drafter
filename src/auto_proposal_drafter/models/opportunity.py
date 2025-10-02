from __future__ import annotations

from datetime import date
from typing import Literal, Sequence

from pydantic import BaseModel, EmailStr, Field


class OpportunityAssets(BaseModel):
    copy: bool | None = Field(default=None, description="Whether marketing copy is provided")
    photo: bool | None = Field(default=None, description="Whether photography assets are provided")
    logo: bool | None = Field(default=None, description="Whether logo assets are provided")


class Opportunity(BaseModel):
    id: str
    company: str
    title: str
    goal: str
    kpi: Sequence[str] = Field(default_factory=list)
    deadline: date | None = None
    budget_band: str | None = None
    persona: str | None = None
    must_have: Sequence[str] = Field(default_factory=list, alias="must_have")
    references: Sequence[str] = Field(default_factory=list)
    constraints: Sequence[str] = Field(default_factory=list)
    assets: OpportunityAssets = Field(default_factory=OpportunityAssets)
    notes: str | None = None
    created_by: EmailStr | None = None
    source: Literal["notion", "slack", "manual", "hubspot", "unknown"] = "unknown"

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "OPP-2025-001",
                "company": "dot.homes",
                "title": "新LP制作",
                "goal": "リード獲得",
                "kpi": ["CVR", "送信数"],
                "deadline": "2025-11-30",
                "budget_band": "〜600万",
                "persona": "B2B 情シス／内製化・CV鈍化が課題",
                "must_have": ["問い合わせフォーム", "実績掲載", "GA4計測"],
                "references": ["https://example.com"],
                "constraints": ["ブランドカラー厳守"],
                "assets": {"copy": False, "photo": True, "logo": True},
                "notes": "短納期。一部CMS化",
                "created_by": "sales@company.com",
                "source": "notion",
            }
        }


__all__ = ["Opportunity", "OpportunityAssets"]
