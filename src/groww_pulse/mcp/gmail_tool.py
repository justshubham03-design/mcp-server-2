import os
from typing import Dict, Any, Optional
from .client import MCPClient

class GmailMCPTool:
    """Wrapper for Gmail MCP Server Tool to create draft emails with the pulse summary and Doc pointer."""
    def __init__(self, client: Optional[MCPClient] = None):
        self.client = client or MCPClient(
            server_command=os.getenv("GMAIL_MCP_COMMAND"),
            output_dir=os.getenv("OUTPUT_DIR", "./output")
        )

    async def create_draft(
        self,
        to: str,
        subject: str,
        body_html: str,
        doc_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calls the create_draft tool on the Gmail MCP server."""
        payload = {
            "to": to,
            "subject": subject,
            "body_html": body_html,
            "doc_url": doc_url or ""
        }
        return await self.client.call_tool("create_draft", payload)
