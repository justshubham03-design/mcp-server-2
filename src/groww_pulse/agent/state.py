from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from ..ingestion.models import ReviewItem
from ..sanitization.pii_cleaner import SanitizedReview
from ..theming.clusterer import ThemeClusterResult
from ..synthesis.schemas import WeeklyPulse, PulseValidationResult

class AgentState(TypedDict):
    """LangGraph state schema maintaining end-to-end pulse workflow state."""
    # Pipeline Parameters
    package_id: str
    weeks_lookback: int
    max_reviews: int
    email_recipient: str
    use_mock: bool
    dry_run: bool

    # Data Layers
    raw_reviews: List[Dict[str, Any]]
    sanitized_reviews: List[Dict[str, Any]]
    clusters: List[Dict[str, Any]]

    # Synthesis & Validation
    weekly_pulse: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    retry_count: int
    max_retries: int

    # MCP Deliverables
    markdown_content: Optional[str]
    html_email_content: Optional[str]
    doc_id: Optional[str]
    doc_url: Optional[str]
    draft_id: Optional[str]
    status: str
    errors: List[str]
