from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, Field


class SectionSpec(BaseModel):
    kind: str
    variant: str
    copy: Sequence[str] | None = None
    notes: Sequence[str] | None = None


class SitePageSpec(BaseModel):
    page_id: str
    type: str = Field(default="LP")
    goal: str | None = None
    sections: Sequence[SectionSpec] = Field(default_factory=list)
    notes: Sequence[str] | None = None


class StructureDraft(BaseModel):
    site_map: Sequence[SitePageSpec]
    flows: Sequence[str]
    uncertains: Sequence[str] = Field(default_factory=list)
    risks: Sequence[str] = Field(default_factory=list)


__all__ = ["SectionSpec", "SitePageSpec", "StructureDraft"]
