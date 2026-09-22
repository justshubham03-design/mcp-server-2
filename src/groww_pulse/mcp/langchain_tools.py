import asyncio
from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from .docs_tool import GoogleDocsMCPTool
from .gmail_tool import GmailMCPTool

class CreateDocInput(BaseModel):
    title: str = Field(..., description="The title of the Google Doc to create")
    content: str = Field(..., description="Markdown content of the weekly review pulse")

class CreateDraftInput(BaseModel):
    to: str = Field(..., description="Target email recipient or alias")
    subject: str = Field(..., description="Subject line of the weekly pulse email")
    body_html: str = Field(..., description="Formatted HTML body of the email")
    doc_url: Optional[str] = Field(default="", description="URL/Link to the published Google Doc")

class GoogleDocsLangChainTool(BaseTool):
    name: str = "google_docs_create_document"
    description: str = "Creates a Google Doc containing the weekly review pulse via Google Docs MCP."
    args_schema: Type[BaseModel] = CreateDocInput
    tool_impl: Optional[GoogleDocsMCPTool] = None

    def _run(self, title: str, content: str) -> str:
        impl = self.tool_impl or GoogleDocsMCPTool()
        result = asyncio.run(impl.create_document(title, content))
        return result.get("doc_url") or result.get("message", "Document created successfully")

    async def _arun(self, title: str, content: str) -> str:
        impl = self.tool_impl or GoogleDocsMCPTool()
        result = await impl.create_document(title, content)
        return result.get("doc_url") or result.get("message", "Document created successfully")

class GmailLangChainTool(BaseTool):
    name: str = "gmail_create_draft"
    description: str = "Creates an email draft in Gmail containing the weekly review pulse via Gmail MCP."
    args_schema: Type[BaseModel] = CreateDraftInput
    tool_impl: Optional[GmailMCPTool] = None

    def _run(self, to: str, subject: str, body_html: str, doc_url: Optional[str] = None) -> str:
        impl = self.tool_impl or GmailMCPTool()
        result = asyncio.run(impl.create_draft(to, subject, body_html, doc_url))
        return result.get("draft_id") or result.get("message", "Draft created successfully")

    async def _arun(self, to: str, subject: str, body_html: str, doc_url: Optional[str] = None) -> str:
        impl = self.tool_impl or GmailMCPTool()
        result = await impl.create_draft(to, subject, body_html, doc_url)
        return result.get("draft_id") or result.get("message", "Draft created successfully")
