from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class ReviewItem(BaseModel):
    """Normalized review schema across the ingestion and processing pipeline."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    review_id: str = Field(..., description="Unique identifier or hash of the review")
    source: str = Field(default="google_play", description="Platform source (google_play)")
    app_id: str = Field(default="com.nextbillion.groww", description="Target application package ID")
    date: datetime = Field(..., description="Timestamp when review was submitted")
    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 to 5")
    title: Optional[str] = Field(default=None, description="Review title if provided")
    text: str = Field(..., description="Review body text")
    thumbs_up: int = Field(default=0, ge=0, description="Thumbs up engagement count")
    app_version: Optional[str] = Field(default=None, description="App version installed by reviewer")
    reviewer_name: Optional[str] = Field(default=None, description="Original reviewer display name (to be anonymized)")
