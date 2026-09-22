import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Model Context Protocol (MCP) client communicating via HTTP or JSON-RPC 2.0 stdio protocol.
    Includes built-in local file backup engine for offline/dry-run resilience.
    """
    def __init__(
        self,
        server_command: Optional[str] = None,
        server_url: Optional[str] = None,
        output_dir: str = "./output"
    ):
        self.server_command = server_command or os.getenv("MCP_SERVER_COMMAND")
        self.server_url = server_url or os.getenv("MCP_SERVER_URL") or os.getenv("RAILWAY_URL")
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an MCP tool call via Remote HTTP or local stdio JSON-RPC. If no live MCP server
        is available or if requests fail, it uses the local fallback engine.
        """
        if self.server_url:
            try:
                return await self._call_http_tool(tool_name, arguments)
            except Exception as e:
                logger.warning(f"Remote HTTP MCP server ({self.server_url}) call failed ({e}). Falling back.")

        if self.server_command:
            try:
                return await self._call_stdio_tool(tool_name, arguments)
            except Exception as e:
                logger.warning(f"Live stdio MCP server call failed ({e}). Falling back to local MCP engine.")

        return self._local_fallback_call(tool_name, arguments)

    async def _call_http_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches JSON-RPC message to a remote MCP HTTP endpoint (e.g. Railway)."""
        import httpx
        url = self.server_url.rstrip("/")
        if not url.endswith("/mcp") and not url.endswith("/api/mcp/rpc"):
            endpoint = f"{url}/mcp"
        else:
            endpoint = url

        request_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=request_payload)
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise RuntimeError(f"Remote MCP server returned error: {data['error']}")

        return data.get("result", {})

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
        """Generates structured deliverables adhering to the MCP tool specification with live API bridge."""
        if tool_name in ("create_document", "google_docs_create", "google_docs_append"):
            title = arguments.get("title", "Groww Weekly Pulse")
            content = arguments.get("content", "")
            doc_id_arg = arguments.get("documentId") or arguments.get("doc_id") or os.getenv("GOOGLE_DOCS_ID")

            safe_filename = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in title) + ".md"
            file_path = os.path.join(self.output_dir, safe_filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            doc_id = doc_id_arg or f"local_doc_{abs(hash(file_path)) % 1000000:06d}"
            doc_url = f"https://docs.google.com/document/d/{doc_id_arg}" if doc_id_arg else f"file://{os.path.abspath(file_path)}"

            # Attempt live Google Docs append if doc_id is available
            if doc_id_arg:
                try:
                    from src.mcp_server.services.docs_service import GoogleDocsService
                    from src.mcp_server.schemas.tool_schemas import GoogleDocsAppendInput
                    docs_service = GoogleDocsService()
                    docs_service.append_content(GoogleDocsAppendInput(documentId=doc_id_arg, content=content))
                    logger.info(f"[Live MCP Docs] Appended pulse notes to Google Doc: {doc_id_arg}")
                except Exception as e:
                    logger.warning(f"[Live MCP Docs] Could not append to live Google Doc ({e}). Saved locally to {file_path}")

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
            to_list = [to] if isinstance(to, str) else list(to)
            subject = arguments.get("subject", "Groww Weekly Review Pulse")
            body_html = arguments.get("body_html") or arguments.get("body", "")
            doc_url = arguments.get("doc_url", "")

            safe_filename = "gmail_draft_" + "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in subject)[:30] + ".html"
            file_path = os.path.join(self.output_dir, safe_filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(body_html)

            draft_id = f"local_draft_{abs(hash(file_path)) % 1000000:06d}"

            # Attempt live Gmail draft creation if authenticated
            try:
                from src.mcp_server.services.gmail_service import GmailService
                from src.mcp_server.schemas.tool_schemas import GmailCreateDraftInput
                gmail_service = GmailService()
                live_res = gmail_service.create_draft(GmailCreateDraftInput(
                    to=to_list,
                    subject=subject,
                    body=body_html
                ))
                if live_res.get("draftId"):
                    draft_id = live_res["draftId"]
                    logger.info(f"[Live MCP Gmail] Created live Gmail draft with ID: {draft_id}")
            except Exception as e:
                logger.info(f"[MCP Gmail] Live draft creation skipped/failed ({e}). Staged locally at {file_path}")

            logger.info(f"[MCP Gmail] Email draft staged at: {file_path}")

            return {
                "status": "success",
                "draft_id": draft_id,
                "recipient": to_list[0] if to_list else "user@example.com",
                "subject": subject,
                "file_path": file_path,
                "doc_url": doc_url,
                "message": f"Draft email staged successfully for {to_list}"
            }

        elif tool_name in ("send_email", "gmail_send_email"):
            to = arguments.get("to", "user@example.com")
            to_list = [to] if isinstance(to, str) else list(to)
            subject = arguments.get("subject", "Groww Weekly Review Pulse")
            body_html = arguments.get("body_html") or arguments.get("body", "")

            try:
                from src.mcp_server.services.gmail_service import GmailService
                from src.mcp_server.schemas.tool_schemas import GmailSendEmailInput
                gmail_service = GmailService()
                live_res = gmail_service.send_email(GmailSendEmailInput(
                    to=to_list,
                    subject=subject,
                    body=body_html
                ))
                logger.info(f"[Live MCP Gmail] Sent live email to {to_list}. Message ID: {live_res.get('messageId')}")
                return {
                    "status": "success",
                    "messageId": live_res.get("messageId"),
                    "recipientCount": len(to_list),
                    "message": f"Email sent successfully to {to_list}"
                }
            except Exception as e:
                logger.warning(f"[MCP Gmail] Send email failed ({e}). Staging draft as fallback.")
                return self._local_fallback_call("gmail_create_draft", arguments)

        else:
            raise ValueError(f"Unknown MCP tool: {tool_name}")
