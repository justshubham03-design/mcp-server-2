import pytest
from src.groww_pulse.agent.graph import build_pulse_agent_graph
from src.groww_pulse.agent.state import AgentState

@pytest.mark.asyncio
async def test_langgraph_agent_pipeline_mock():
    graph = build_pulse_agent_graph()

    initial_state: AgentState = {
        "package_id": "com.nextbillion.groww",
        "weeks_lookback": 8,
        "max_reviews": 50,
        "email_recipient": "pm@groww.in",
        "use_mock": True,
        "dry_run": True,
        "raw_reviews": [],
        "sanitized_reviews": [],
        "clusters": [],
        "weekly_pulse": None,
        "validation_result": None,
        "retry_count": 0,
        "max_retries": 3,
        "markdown_content": None,
        "html_email_content": None,
        "doc_id": None,
        "doc_url": None,
        "draft_id": None,
        "status": "initialized",
        "errors": []
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state["status"] == "completed"
    assert len(final_state["sanitized_reviews"]) > 0
    assert len(final_state["clusters"]) <= 5
    
    pulse = final_state["weekly_pulse"]
    assert pulse is not None
    assert len(pulse["top_themes"]) == 3
    assert len(pulse["verbatim_quotes"]) == 3
    assert len(pulse["action_ideas"]) == 3
    assert pulse["word_count"] <= 250

    val = final_state["validation_result"]
    assert val is not None
    assert val["is_valid"] is True
    assert all(val["quotes_verified"])

    assert final_state["doc_id"] is not None
    assert final_state["draft_id"] is not None
