from typing import List, Optional
from pydantic import BaseModel, Field

class ThemeItem(BaseModel):
    """Structured item for a top user theme in the weekly pulse."""
    rank: int = Field(..., description="Theme priority rank (1, 2, or 3)")
    name: str = Field(..., description="Theme title, e.g. Payments, UPI & Withdrawals")
    metric: str = Field(..., description="Volume % and avg rating, e.g. '34% volume, 1.7★ avg rating'")
    summary: str = Field(..., description="1-2 sentence scannable summary of user sentiment and key problem/delight")

class WeeklyPulse(BaseModel):
    """One-page Weekly Executive Review Pulse schema (constrained to <= 250 words total)."""
    week_identifier: str = Field(..., description="Week identifier, e.g. '2026-W38'")
    analysis_period_start: str = Field(..., description="Start date of lookback window, e.g. '2026-07-25'")
    analysis_period_end: str = Field(..., description="End date of lookback window, e.g. '2026-09-19'")
    total_reviews_analyzed: int = Field(..., description="Total count of reviews analyzed in this pulse")
    word_count: int = Field(default=0, description="Computed word count of the executive pulse note (must be <= 250)")
    executive_summary: str = Field(
        ...,
        description="High-level pulse overview (2-3 sentences max) capturing overall sentiment, primary driver of friction, and key win."
    )
    top_themes: List[ThemeItem] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly the Top 3 themes users are talking about most."
    )
    verbatim_quotes: List[str] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 authentic, verbatim snippets from real reviews (no invented wording, no PII)."
    )
    action_ideas: List[str] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 concrete, cross-functional action steps grounded directly in the themes (for Product, Eng, Support)."
    )

class PulseValidationResult(BaseModel):
    is_valid: bool
    word_count: int
    max_word_limit: int = 250
    quotes_verified: List[bool] = Field(default_factory=list)
    unmatched_quotes: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
