import logging
from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    ingest_and_sanitize_node,
    theming_node,
    synthesis_node,
    validation_node,
    mcp_dispatch_node
)

logger = logging.getLogger(__name__)

def should_retry(state: AgentState) -> str:
    """Conditional routing edge: checks if validation passed or if retries remain."""
    val_res = state.get("validation_result") or {}
    is_valid = val_res.get("is_valid", False)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if is_valid:
        return "mcp_dispatch"
    elif retry_count < max_retries:
        logger.warning(f"[LangGraph Router] Validation failed. Retrying synthesis (attempt {retry_count + 1}/{max_retries})...")
        return "synthesis"
    else:
        logger.warning(f"[LangGraph Router] Reached max retries ({max_retries}). Proceeding to MCP dispatch with fallback output.")
        return "mcp_dispatch"

def build_pulse_agent_graph() -> StateGraph:
    """Constructs and compiles the complete LangGraph StateGraph workflow for Groww Review Pulse AI."""
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("ingest_and_sanitize", ingest_and_sanitize_node)
    workflow.add_node("theming", theming_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("mcp_dispatch", mcp_dispatch_node)

    # 2. Add Edges
    workflow.set_entry_point("ingest_and_sanitize")
    workflow.add_edge("ingest_and_sanitize", "theming")
    workflow.add_edge("theming", "synthesis")
    workflow.add_edge("synthesis", "validation")

    # 3. Conditional Edge for Validation & Self-Correction
    workflow.add_conditional_edges(
        "validation",
        should_retry,
        {
            "synthesis": "synthesis",
            "mcp_dispatch": "mcp_dispatch"
        }
    )

    workflow.add_edge("mcp_dispatch", END)

    return workflow.compile()
