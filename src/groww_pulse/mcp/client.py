import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Model Context Protocol (MCP) client communicating via JSON-RPC 2.0 stdio protocol.
    Includes built-in local file backup engine for offline/dry-run resilience.
    """
    def __init__(self, server_command: Optional[str] = None, output_dir: str = "./output"):
        self.server_command = server_command
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an MCP tool call via JSON-RPC. If no live MCP server is running or if stdio fails,
        it uses the local fallback engine to generate the deliverable locally.
        """
        if self.server_command:
            try:
                return await self._call_stdio_tool(tool_name, arguments)
            except Exception as e:
                logger.warning(f"Live MCP server call failed ({e}). Falling back to local MCP engine.")

        return self._local_fallback_call(tool_name, arguments)

    async def _call_stdio_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches JSON-RPC message to an external MCP server subprocess."""
        proc = await asyncio.create_subprocess_shell(
            self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        request_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        request_bytes = (json.dumps(request_payload) + "\n").encode("utf-8")
        stdout, stderr = await proc.communicate(input=request_bytes)

        if proc.returncode != 0:
            raise RuntimeError(f"MCP server exited with code {proc.returncode}: {stderr.decode()}")

        response = json.loads(stdout.decode().strip())
        if "error" in response:
            raise RuntimeError(f"MCP server returned error: {response['error']}")

        return response.get("result", {})

    def _local_fallback_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Generates structured local deliverables adhering to the MCP tool specification."""
        if tool_name in ("create_document", "google_docs_create"):
            title = arguments.get("title", "Groww Weekly Pulse")
            content = arguments.get("content", "")
            safe_filename = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in title) + ".md"
            file_path = os.path.join(self.output_dir, safe_filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            doc_id = f"local_doc_{abs(hash(file_path)) % 1000000:06d}"
            doc_url = f"file://{os.path.abspath(file_path)}"
            logger.info(f"[MCP Docs] Document generated locally at: {file_path}")

            return {
                "status": "success",
                "doc_id": doc_id,
                "doc_url": doc_url,
                "file_path": file_path,
                "message": f"Document created successfully at {file_path}"
            }

        elif tool_name in ("create_draft", "gmail_create_draft"):
            to = arguments.get("to", "user@example.com")
            subject = arguments.get("subject", "Groww Weekly Review Pulse")
            body_html = arguments.get("body_html", "")
            doc_url = arguments.get("doc_url", "")

            safe_filename = "gmail_draft_" + "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in subject)[:30] + ".html"
            file_path = os.path.join(self.output_dir, safe_filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(body_html)

            draft_id = f"local_draft_{abs(hash(file_path)) % 1000000:06d}"
            logger.info(f"[MCP Gmail] Email draft staged locally at: {file_path}")

            return {
                "status": "success",
                "draft_id": draft_id,
                "recipient": to,
                "subject": subject,
                "file_path": file_path,
                "doc_url": doc_url,
                "message": f"Draft email created successfully for {to}"
            }

        else:
            raise ValueError(f"Unknown MCP tool: {tool_name}")
