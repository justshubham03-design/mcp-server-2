import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from .state import AgentState
from ..ingestion.play_store import PlayStoreIngestion
from ..ingestion.models import ReviewItem
from ..sanitization.pii_cleaner import PIISanitizer, SanitizedReview
from ..theming.clusterer import ThemeClusterer, ThemeClusterResult
from ..synthesis.schemas import WeeklyPulse, PulseValidationResult
from ..synthesis.validator import PulseValidator
from ..synthesis.pulse_builder import PulseBuilder
from ..mcp.docs_tool import GoogleDocsMCPTool
from ..mcp.gmail_tool import GmailMCPTool

logger = logging.getLogger(__name__)

async def ingest_and_sanitize_node(state: AgentState) -> Dict[str, Any]:
    """Phase 1: Ingestion & PII / Emoji / <8 words sanitization."""
    logger.info("[LangGraph Agent] Running Ingestion & Sanitization Node...")
    package_id = state.get("package_id", "com.nextbillion.groww")
    weeks = state.get("weeks_lookback", 8)
    max_revs = state.get("max_reviews", 1000)
    use_mock = state.get("use_mock", False)

    if use_mock:
        raw_items = PlayStoreIngestion.generate_mock_groww_reviews(weeks_lookback=weeks, count=50)
    else:
        ingestion = PlayStoreIngestion(package_id=package_id)
        raw_items = ingestion.fetch_reviews(weeks_lookback=weeks, max_reviews=max_revs, use_cache_fallback=True)

    sanitizer = PIISanitizer(min_words=8, strip_emojis=True, filter_noise=True, redact_pii=True)
    sanitized_items = sanitizer.sanitize_reviews(raw_items)

    return {
        "raw_reviews": [r.model_dump() for r in raw_items],
        "sanitized_reviews": [r.model_dump() for r in sanitized_items],
        "status": "ingested_and_sanitized"
    }

async def theming_node(state: AgentState) -> Dict[str, Any]:
    """Phase 2: Thematic Clustering (Max 5 Themes)."""
    logger.info("[LangGraph Agent] Running Theming & Taxonomy Node...")
    sanitized_dicts = state.get("sanitized_reviews", [])
    sanitized_objs = [SanitizedReview(**d) for d in sanitized_dicts]

    clusterer = ThemeClusterer(max_themes=5, top_themes_count=3)
    cluster_results = clusterer.cluster(sanitized_objs)

    return {
        "clusters": [c.model_dump() for c in cluster_results],
        "status": "themed"
    }

async def synthesis_node(state: AgentState) -> Dict[str, Any]:
    """Phase 2: Pulse Synthesis using Groq LLM (or deterministic fallback)."""
    logger.info("[LangGraph Agent] Running Synthesis Node (Groq LLM / Grounded Builder)...")
    cluster_dicts = state.get("clusters", [])
    sanitized_dicts = state.get("sanitized_reviews", [])
    retry_count = state.get("retry_count", 0)

    cluster_objs = [ThemeClusterResult(**d) for d in cluster_dicts]
    sanitized_objs = [SanitizedReview(**d) for d in sanitized_dicts]

    # Initialize PulseBuilder with Phase 2 Groq provider
    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    builder = PulseBuilder(llm_provider="groq", api_key=groq_api_key, model_name=groq_model)

    if groq_api_key:
        pulse = builder.synthesize_with_llm(cluster_objs, sanitized_objs)
    else:
        pulse = builder.build_deterministic_pulse(cluster_objs, sanitized_objs)

    return {
        "weekly_pulse": pulse.model_dump(),
        "retry_count": retry_count + 1,
        "status": "synthesized"
    }

async def validation_node(state: AgentState) -> Dict[str, Any]:
    """Validation: Verifies <= 250 words and exact verbatim quote grounding."""
    logger.info("[LangGraph Agent] Running Guardrail & Grounding Validation Node...")
    pulse_dict = state.get("weekly_pulse")
    sanitized_dicts = state.get("sanitized_reviews", [])

    if not pulse_dict:
        return {
            "validation_result": {"is_valid": False, "errors": ["No pulse generated"]},
            "status": "validation_failed"
        }

    pulse_obj = WeeklyPulse(**pulse_dict)
    sanitized_objs = [SanitizedReview(**d) for d in sanitized_dicts]

    validator = PulseValidator(max_word_limit=250, required_quotes=3, required_actions=3)
    val_result = validator.validate(pulse_obj, sanitized_objs)

    # Render Markdown & HTML formats
    builder = PulseBuilder()
    md_content = builder.render_markdown(pulse_obj)
    html_content = builder.render_html_email(pulse_obj)

    return {
        "weekly_pulse": pulse_obj.model_dump(),
        "validation_result": val_result.model_dump(),
        "markdown_content": md_content,
        "html_email_content": html_content,
        "errors": val_result.errors,
        "status": "validated" if val_result.is_valid else "validation_failed"
    }

async def mcp_dispatch_node(state: AgentState) -> Dict[str, Any]:
    """Phase 3: MCP Dispatcher (Google Docs & Gmail Tools)."""
    logger.info("[LangGraph Agent] Running MCP Dispatch Node (Google Docs & Gmail)...")
    pulse_dict = state.get("weekly_pulse", {})
    md_content = state.get("markdown_content", "")
    html_content = state.get("html_email_content", "")
    recipient = state.get("email_recipient", "user@example.com")
    week_id = pulse_dict.get("week_identifier", "Weekly")

    # 1. Google Docs MCP Tool
    docs_tool = GoogleDocsMCPTool()
    doc_title = f"Groww Weekly Review Pulse - {week_id}"
    doc_resp = await docs_tool.create_document(title=doc_title, content=md_content)
    doc_id = doc_resp.get("doc_id")
    doc_url = doc_resp.get("doc_url", "")

    # Re-render HTML email with the doc link
    pulse_obj = WeeklyPulse(**pulse_dict)
    builder = PulseBuilder()
    final_html = builder.render_html_email(pulse_obj, doc_url=doc_url)

    # 2. Gmail MCP Tool
    gmail_tool = GmailMCPTool()
    email_subject = f"[Weekly Pulse] Groww User Feedback & Action Items ({week_id})"
    draft_resp = await gmail_tool.create_draft(
        to=recipient,
        subject=email_subject,
        body_html=final_html,
        doc_url=doc_url
    )
    draft_id = draft_resp.get("draft_id")

    return {
        "doc_id": doc_id,
        "doc_url": doc_url,
        "draft_id": draft_id,
        "html_email_content": final_html,
        "status": "completed"
    }
