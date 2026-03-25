from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StockOpportunity(BaseModel):
    ticker: str | None = Field(default=None, description="Stock ticker if identifiable")
    alert_type: Literal[
        "upcoming_ipo",
        "policy_announcement",
        "sector_rotation",
        "basket_buying",
        "earnings_catalyst",
        "general_insight",
    ]
    confidence: float = Field(ge=0, le=1, description="Confidence 0-1")
    urgency: Literal["urgent", "standard", "low"]
    reasoning: str = Field(description="2-3 sentence explanation")
    action_suggestion: str = Field(description="What an investor might consider")
    related_tickers: list[str] = Field(default_factory=list)
    time_sensitivity: str = Field(description="e.g. 'next 24 hours', 'this week'")


class AnalysisResult(BaseModel):
    opportunities: list[StockOpportunity]
    market_summary: str = Field(description="1-2 sentence overall market mood")
