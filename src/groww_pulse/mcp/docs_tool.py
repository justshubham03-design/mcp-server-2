import os
from typing import Dict, Any, Optional
from .client import MCPClient

class GoogleDocsMCPTool:
    """Wrapper for Google Docs MCP Server Tool to create or update documents."""
    def __init__(self, client: Optional[MCPClient] = None):
        self.client = client or MCPClient(
            server_command=os.getenv("GOOGLE_DOCS_MCP_COMMAND"),
            output_dir=os.getenv("OUTPUT_DIR", "./output")
        )

    async def create_document(self, title: str, content: str) -> Dict[str, Any]:
        """Calls the create_document tool on the Google Docs MCP server."""
        payload = {
            "title": title,
            "content": content
        }
        return await self.client.call_tool("create_document", payload)
