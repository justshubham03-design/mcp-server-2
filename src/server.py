#!/usr/bin/env python3
"""
FastAPI Cloud Web & Trigger Server for Groww Review Pulse AI.
Provides REST endpoints for health checks, on-demand pulse execution, and MCP deliverables.
"""

import os
import sys
from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

# Ensure root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from src.groww_pulse.agent.graph import build_pulse_agent_graph
from src.groww_pulse.agent.state import AgentState
from src.mcp_server.server import MCPServer

app = FastAPI(
    title="Groww Review Pulse AI - Cloud Service",
    description="Automated AI Agent Pipeline analyzing Play Store user feedback for Groww with multi-LLM synthesis and MCP delivery.",
    version="1.0.0"
)

class PulseRequest(BaseModel):
    weeks: int = Field(default=8, ge=1, le=52, description="Number of historical weeks to analyze")
    email: Optional[str] = Field(default=None, description="Optional recipient email for staging draft")
    doc_id: Optional[str] = Field(default=None, description="Optional Google Doc ID to append pulse notes")
    use_mock: bool = Field(default=False, description="Whether to use cached mock reviews")

@app.get("/")
def root():
    return {
        "service": "Groww Review Pulse AI",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "generate_pulse": "POST /api/pulse/generate",
            "latest_pulse": "/api/pulse/latest",
            "mcp_tools": "/api/mcp/tools"
        }
    }

@app.get("/health")
def health_check():
    """Railway health check endpoint."""
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_google_token = bool(os.getenv("GOOGLE_TOKEN_JSON") or os.getenv("GOOGLE_TOKEN_BASE64") or os.path.exists("./.config/google_token.json"))

    return {
        "status": "healthy",
        "services": {
            "groq_configured": has_groq,
            "gemini_configured": has_gemini,
            "google_mcp_authenticated": has_google_token
        }
    }

@app.get("/api/mcp/tools")
def list_mcp_tools():
    """Returns available MCP tools."""
    server = MCPServer()
    return {"tools": server.get_tool_definitions()}

@app.post("/mcp")
@app.post("/api/mcp/rpc")
async def handle_mcp_rpc(request: dict):
    """Standard JSON-RPC 2.0 MCP endpoint over HTTP."""
    server = MCPServer()
    return await server.handle_request(request)

@app.post("/api/mcp/call/{tool_name}")
async def call_mcp_tool_rest(tool_name: str, arguments: dict):
    """REST wrapper to execute an MCP tool call directly."""
    server = MCPServer()
    rpc_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    res = await server.handle_request(rpc_req)
    return res.get("result", {})

@app.get("/api/pulse/latest")
def get_latest_pulse():
    """Returns the most recently generated pulse markdown document."""
    output_dir = Path("./output")
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No pulse outputs generated yet.")
    
    md_files = sorted(output_dir.glob("Groww_Weekly_Review_Pulse_*.md"), reverse=True)
    if not md_files:
        raise HTTPException(status_code=404, detail="No pulse reports found.")
    
    latest_file = md_files[0]
    return PlainTextResponse(latest_file.read_text(encoding="utf-8"), media_type="text/markdown")

@app.post("/api/pulse/generate")
def generate_pulse(req: PulseRequest):
    """Triggers the full Groww Review Pulse Agent pipeline synchronously."""
    try:
        app_graph = build_pulse_agent_graph()
        initial_state: AgentState = {
            "package_id": os.getenv("PLAY_STORE_PACKAGE_ID", "com.nextbillion.groww"),
            "weeks_lookback": req.weeks,
            "max_reviews": int(os.getenv("MAX_REVIEWS_TO_FETCH", 1000)),
            "email_recipient": req.email or os.getenv("DEFAULT_EMAIL_RECIPIENT", "leadership@groww.in"),
            "use_mock": req.use_mock,
            "dry_run": False,
            "raw_reviews": [],
            "sanitized_reviews": [],
            "clusters": [],
            "weekly_pulse": None,
            "validation_result": None,
            "retry_count": 0,
            "max_retries": 3,
            "markdown_content": None,
            "html_email_content": None,
            "doc_id": req.doc_id,
            "doc_url": None,
            "draft_id": None,
            "status": "pending",
            "errors": []
        }

        final_state = app_graph.invoke(initial_state)

        if final_state.get("status") == "error":
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": final_state.get("errors", [])
                }
            )

        pulse = final_state.get("weekly_pulse")
        val_res = final_state.get("validation_result") or {}
        return {
            "status": "success",
            "week_identifier": pulse.get("week_identifier") if pulse else None,
            "total_reviews": len(final_state.get("sanitized_reviews", [])),
            "word_count": val_res.get("total_word_count", 0),
            "validation_passed": val_res.get("is_valid", False),
            "top_themes": [t.get("theme_name") for t in pulse.get("top_themes", [])] if pulse else [],
            "draft_id": final_state.get("draft_id"),
            "doc_url": final_state.get("doc_url")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("src.server:app", host="0.0.0.0", port=port, reload=False)
