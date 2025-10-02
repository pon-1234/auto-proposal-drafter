from __future__ import annotations

from typing import Mapping, Sequence

from pydantic import BaseModel, Field


class WireProject(BaseModel):
    id: str
    title: str


class WireSection(BaseModel):
    kind: str
    variant: str
    placeholders: Mapping[str, str] | None = None


class WirePage(BaseModel):
    page_id: str
    sections: Sequence[WireSection] = Field(default_factory=list)
    notes: Sequence[str] | None = None


class WireDraft(BaseModel):
    project: WireProject
    frames: Sequence[str] = Field(default_factory=lambda: ["Desktop", "Tablet", "Mobile"])
    pages: Sequence[WirePage]


__all__ = ["WireDraft", "WirePage", "WireProject", "WireSection"]
