import os
import pytest
import tempfile
from src.groww_pulse.mcp import MCPClient, GoogleDocsMCPTool, GmailMCPTool

@pytest.mark.asyncio
async def test_mcp_local_fallback_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = MCPClient(output_dir=tmpdir)

        # Test Google Docs local fallback
        doc_resp = await client.call_tool("create_document", {
            "title": "Groww Pulse Test",
            "content": "# Test Header\nSample weekly note content."
        })
        assert doc_resp["status"] == "success"
        assert "file_path" in doc_resp
        assert os.path.exists(doc_resp["file_path"])

        # Test Gmail Draft local fallback
        draft_resp = await client.call_tool("create_draft", {
            "to": "test@example.com",
            "subject": "Weekly Pulse Subject",
            "body_html": "<p>Sample HTML content</p>",
            "doc_url": doc_resp["doc_url"]
        })
        assert draft_resp["status"] == "success"
        assert draft_resp["recipient"] == "test@example.com"
        assert os.path.exists(draft_resp["file_path"])

@pytest.mark.asyncio
async def test_mcp_tools_wrappers():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = MCPClient(output_dir=tmpdir)
        docs_tool = GoogleDocsMCPTool(client=client)
        gmail_tool = GmailMCPTool(client=client)

        doc_res = await docs_tool.create_document("Doc 1", "Content 1")
        assert doc_res["status"] == "success"

        draft_res = await gmail_tool.create_draft("alias@groww.in", "Subject", "<h1>Pulse</h1>", doc_res["doc_url"])
        assert draft_res["status"] == "success"
