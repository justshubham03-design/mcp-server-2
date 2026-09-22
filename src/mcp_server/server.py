import sys
import json
import asyncio
from typing import Dict, Any, Optional, List

from .services.gmail_service import GmailService
from .services.docs_service import GoogleDocsService
from .schemas.tool_schemas import (
    GmailCreateDraftInput,
    GmailSendEmailInput,
    GoogleDocsAppendInput
)
from .utils.errors import MCPError, ErrorCode
from .utils.logger import get_sanitized_logger

logger = get_sanitized_logger(__name__)

class MCPServer:
    """Standard Model Context Protocol (MCP) Server for Gmail and Google Docs."""
    def __init__(
        self,
        gmail_service: Optional[GmailService] = None,
        docs_service: Optional[GoogleDocsService] = None
    ):
        self.gmail_service = gmail_service or GmailService()
        self.docs_service = docs_service or GoogleDocsService()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns the declared MCP tool schemas and descriptions."""
        return [
            {
                "name": "gmail_create_draft",
                "description": (
                    "Create a Gmail draft without sending it. "
                    "Use this tool when the user wants an email prepared for review, "
                    "but does not explicitly ask for it to be sent."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of recipient email addresses (at least one required)."
                        },
                        "cc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of CC recipient email addresses."
                        },
                        "bcc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of BCC recipient email addresses."
                        },
                        "subject": {
                            "type": "string",
                            "description": "Subject line of the email."
                        },
                        "body": {
                            "type": "string",
                            "description": "Body content of the email (plain text)."
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "gmail_send_email",
                "description": (
                    "Send an email immediately using the authenticated Gmail account. "
                    "This performs an external side effect and sends the message to the "
                    "specified recipients. Use only when the user explicitly requests "
                    "sending the email."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of recipient email addresses (at least one required)."
                        },
                        "cc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of CC recipient email addresses."
                        },
                        "bcc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of BCC recipient email addresses."
                        },
                        "subject": {
                            "type": "string",
                            "description": "Subject line of the email."
                        },
                        "body": {
                            "type": "string",
                            "description": "Body content of the email (plain text)."
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "google_docs_append",
                "description": (
                    "Append text to the end of an existing Google Doc. "
                    "This modifies the specified document by adding content at the end, "
                    "but does not delete or replace existing content."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "documentId": {
                            "type": "string",
                            "description": "The unique document ID of the target Google Doc."
                        },
                        "content": {
                            "type": "string",
                            "description": "Text content to append to the document."
                        },
                        "addNewline": {
                            "type": "boolean",
                            "default": True,
                            "description": "Whether to ensure content begins on a new line (default: true)."
                        }
                    },
                    "required": ["documentId", "content"]
                }
            }
        ]

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the requested MCP tool and returns structured result."""
        logger.info(f"Invoking tool '{name}'...")
        try:
            if name == "gmail_create_draft":
                validated_input = GmailCreateDraftInput(**arguments)
                return self.gmail_service.create_draft(validated_input)

            elif name == "gmail_send_email":
                validated_input = GmailSendEmailInput(**arguments)
                return self.gmail_service.send_email(validated_input)

            elif name == "google_docs_append":
                validated_input = GoogleDocsAppendInput(**arguments)
                return self.docs_service.append_content(validated_input)

            else:
                raise MCPError(ErrorCode.INTERNAL_ERROR, f"Unknown tool: '{name}'")

        except MCPError as e:
            logger.error(f"Tool '{name}' failed with MCPError: {e.message}")
            return e.to_dict()
        except Exception as e:
            logger.error(f"Unexpected error in tool '{name}': {e}")
            return MCPError(ErrorCode.VALIDATION_ERROR, str(e)).to_dict()

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processes a single JSON-RPC 2.0 request."""
        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "google-workspace-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }

        elif method == "notifications/initialized":
            logger.info("Client initialization handshake complete.")
            return None

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tool_definitions()
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            result = self.handle_tool_call(tool_name, tool_args)

            # Format as standard MCP CallToolResult
            is_error = not result.get("success", True)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ],
                    "isError": is_error
                }
            }

        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    async def run_stdio(self):
        """Runs the MCP server over standard input / output (stdio)."""
        logger.info("Starting Google Workspace MCP Server on stdio...")
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line = await reader.readline()
            if not line:
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                request = json.loads(line_str)
                response = await self.handle_request(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                logger.error(f"Error processing JSON-RPC message: {e}")
                err_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                sys.stdout.write(json.dumps(err_response) + "\n")
                sys.stdout.flush()
