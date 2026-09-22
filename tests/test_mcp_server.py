import pytest
from unittest.mock import MagicMock, patch
from googleapiclient.errors import HttpError
import httplib2

from src.mcp_server.server import MCPServer
from src.mcp_server.schemas.tool_schemas import (
    GmailCreateDraftInput,
    GmailSendEmailInput,
    GoogleDocsAppendInput
)
from src.mcp_server.services.gmail_service import GmailService
from src.mcp_server.services.docs_service import GoogleDocsService
from src.mcp_server.utils.errors import MCPError, ErrorCode

@pytest.mark.asyncio
async def test_mcp_initialize_and_tools_list():
    server = MCPServer()

    # 1. Test initialize
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    init_res = await server.handle_request(init_req)
    assert init_res["result"]["serverInfo"]["name"] == "google-workspace-mcp-server"
    assert "tools" in init_res["result"]["capabilities"]

    # 2. Test tools/list
    list_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list"
    }
    list_res = await server.handle_request(list_req)
    tools = list_res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "gmail_create_draft" in tool_names
    assert "gmail_send_email" in tool_names
    assert "google_docs_append" in tool_names

def test_gmail_schema_validation():
    # Valid input
    valid_draft = GmailCreateDraftInput(
        to=["user@example.com"],
        cc=["cc@example.com"],
        subject="Test Subject",
        body="Test Body"
    )
    assert valid_draft.to == ["user@example.com"]

    # Invalid email format should raise error
    with pytest.raises(MCPError) as exc_info:
        GmailCreateDraftInput(
            to=["not-an-email"],
            subject="Test Subject",
            body="Test Body"
        )
    assert exc_info.value.code == ErrorCode.INVALID_RECIPIENT

def test_google_docs_schema_validation():
    # Valid input
    valid_docs = GoogleDocsAppendInput(
        documentId="doc_12345",
        content="New weekly pulse notes",
        addNewline=True
    )
    assert valid_docs.documentId == "doc_12345"
    assert valid_docs.addNewline is True

    # Missing document ID should fail validation
    with pytest.raises(Exception):
        GoogleDocsAppendInput(documentId="", content="Text")

def test_gmail_service_create_draft_mocked():
    mock_auth = MagicMock()
    service = GmailService(auth_manager=mock_auth)

    mock_gmail_api = MagicMock()
    mock_drafts = mock_gmail_api.users.return_value.drafts.return_value
    mock_drafts.create.return_value.execute.return_value = {
        "id": "draft_999",
        "message": {"id": "msg_888"}
    }

    with patch.object(service, "_get_service", return_value=mock_gmail_api):
        input_data = GmailCreateDraftInput(
            to=["recipient@example.com"],
            subject="Meeting Notes",
            body="Here are the notes from today's discussion."
        )
        result = service.create_draft(input_data)

        assert result["success"] is True
        assert result["draftId"] == "draft_999"
        assert result["messageId"] == "msg_888"

def test_gmail_service_send_email_mocked():
    mock_auth = MagicMock()
    service = GmailService(auth_manager=mock_auth)

    mock_gmail_api = MagicMock()
    mock_messages = mock_gmail_api.users.return_value.messages.return_value
    mock_messages.send.return_value.execute.return_value = {
        "id": "sent_msg_777"
    }

    with patch.object(service, "_get_service", return_value=mock_gmail_api):
        input_data = GmailSendEmailInput(
            to=["recipient@example.com"],
            subject="Urgent Update",
            body="Please find the attached pulse."
        )
        result = service.send_email(input_data)

        assert result["success"] is True
        assert result["messageId"] == "sent_msg_777"
        assert result["recipientCount"] == 1

def test_google_docs_append_structural_indexing_mocked():
    mock_auth = MagicMock()
    docs_service = GoogleDocsService(auth_manager=mock_auth)

    mock_docs_api = MagicMock()
    mock_documents = mock_docs_api.documents.return_value
    
    # Mock existing doc with end index 150
    mock_documents.get.return_value.execute.return_value = {
        "documentId": "doc_abc123",
        "body": {
            "content": [
                {"endIndex": 100},
                {"endIndex": 150}
            ]
        }
    }
    mock_documents.batchUpdate.return_value.execute.return_value = {}

    with patch.object(docs_service, "_get_service", return_value=mock_docs_api):
        input_data = GoogleDocsAppendInput(
            documentId="doc_abc123",
            content="Appended paragraph line.",
            addNewline=True
        )
        result = docs_service.append_content(input_data)

        assert result["success"] is True
        assert result["documentId"] == "doc_abc123"
        # Terminal insert index should be 150 - 1 = 149
        assert result["insertLocationIndex"] == 149

        # Verify batchUpdate call args
        call_args = mock_documents.batchUpdate.call_args[1]
        assert call_args["documentId"] == "doc_abc123"
        req = call_args["body"]["requests"][0]["insertText"]
        assert req["location"]["index"] == 149
        assert req["text"] == "\nAppended paragraph line."

def test_google_docs_not_found_error_handling():
    mock_auth = MagicMock()
    docs_service = GoogleDocsService(auth_manager=mock_auth)

    mock_docs_api = MagicMock()
    mock_documents = mock_docs_api.documents.return_value
    
    resp = httplib2.Response({"status": 404, "reason": "Not Found"})
    mock_documents.get.return_value.execute.side_effect = HttpError(resp, b"Document not found")

    with patch.object(docs_service, "_get_service", return_value=mock_docs_api):
        input_data = GoogleDocsAppendInput(
            documentId="invalid_doc_id",
            content="Text"
        )
        with pytest.raises(MCPError) as exc_info:
            docs_service.append_content(input_data)
        assert exc_info.value.code == ErrorCode.DOCUMENT_NOT_FOUND

@pytest.mark.asyncio
async def test_mcp_server_tool_call_jsonrpc_flow():
    server = MCPServer()

    # Test unknown tool call
    call_req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "non_existent_tool",
            "arguments": {}
        }
    }
    res = await server.handle_request(call_req)
    assert res["result"]["isError"] is True
    assert "INTERNAL_ERROR" in res["result"]["content"][0]["text"]

def test_gmail_html_mime_message_creation():
    import base64
    from email import message_from_bytes
    service = GmailService(auth_manager=MagicMock())
    
    html_content = "<!DOCTYPE html><html><body><h1>Groww Weekly Pulse</h1><p>Executive summary text.</p></body></html>"
    raw_b64 = service._build_mime_message(
        to=["recipient@example.com"],
        subject="Groww Weekly Pulse",
        body=html_content
    )
    
    raw_bytes = base64.urlsafe_b64decode(raw_b64.encode("utf-8"))
    parsed_msg = message_from_bytes(raw_bytes)
    
    assert parsed_msg.is_multipart()
    content_types = [part.get_content_type() for part in parsed_msg.walk()]
    assert "text/plain" in content_types
    assert "text/html" in content_types
