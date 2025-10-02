from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, Field


class EstimateLineItem(BaseModel):
    item: str
    qty: float = 1.0
    hours: float
    rate: float
    role: str
    notes: str | None = None

    @property
    def cost(self) -> float:
        return round(self.qty * self.hours * self.rate, 2)


class EstimateCoefficient(BaseModel):
    name: str
    multiplier: float
    reason: str | None = None


class EstimateDraft(BaseModel):
    line_items: Sequence[EstimateLineItem]
    coefficients: Sequence[EstimateCoefficient] = Field(default_factory=list)
    assumptions: Sequence[str] = Field(default_factory=list)
    currency: str = "JPY"


__all__ = ["EstimateDraft", "EstimateLineItem", "EstimateCoefficient"]
