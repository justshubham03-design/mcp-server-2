import pytest
from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "health" in data["endpoints"]

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data

def test_mcp_tools_endpoint():
    response = client.get("/api/mcp/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    tool_names = [t["name"] for t in data["tools"]]
    assert "gmail_create_draft" in tool_names
    assert "google_docs_append" in tool_names

def test_latest_pulse_endpoint():
    response = client.get("/api/pulse/latest")
    # If outputs exist, returns 200 with markdown
    if response.status_code == 200:
        assert "# Groww Weekly Review Pulse" in response.text
    else:
        assert response.status_code == 404

def test_mcp_jsonrpc_endpoint():
    rpc_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    response = client.post("/mcp", json=rpc_req)
    assert response.status_code == 200
    data = response.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    tool_names = [t["name"] for t in data["result"]["tools"]]
    assert "gmail_create_draft" in tool_names

def test_mcp_call_rest_endpoint_validation():
    response = client.post(
        "/api/mcp/call/gmail_create_draft",
        json={"to": ["invalid-email"], "subject": "Test", "body": "Body"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("isError") is True
    assert "INVALID_RECIPIENT" in data.get("content", [{}])[0].get("text", "")
