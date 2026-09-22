from typing import Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..auth.google_auth import GoogleAuthManager
from ..schemas.tool_schemas import GoogleDocsAppendInput
from ..utils.errors import MCPError, ErrorCode
from ..utils.logger import get_sanitized_logger

logger = get_sanitized_logger(__name__)

class GoogleDocsService:
    """Service wrapping Google Docs API for safe structural content appending."""
    def __init__(self, auth_manager: Optional[GoogleAuthManager] = None):
        self.auth_manager = auth_manager or GoogleAuthManager()

    def _get_service(self):
        creds = self.auth_manager.get_credentials()
        return build("docs", "v1", credentials=creds, cache_discovery=False)

    def append_content(self, input_data: GoogleDocsAppendInput) -> Dict[str, Any]:
        """
        Safely appends text to the end of an existing Google Doc using batchUpdate structural indexing.
        Preserves 100% of existing document content.
        """
        try:
            service = self._get_service()
            doc_id = input_data.documentId

            # 1. Fetch document metadata to inspect structural length
            try:
                doc = service.documents().get(documentId=doc_id).execute()
            except HttpError as e:
                if e.resp.status in (404, 400):
                    raise MCPError(ErrorCode.DOCUMENT_NOT_FOUND, f"Google Doc with ID '{doc_id}' not found or inaccessible.")
                elif e.resp.status == 403:
                    raise MCPError(ErrorCode.DOCUMENT_NOT_FOUND, f"Permission denied accessing Google Doc '{doc_id}'.")
                raise

            # 2. Compute terminal insertion index
            body_content = doc.get("body", {}).get("content", [])
            if not body_content:
                insert_index = 1
            else:
                last_element = body_content[-1]
                end_index = last_element.get("endIndex", 1)
                # Google Docs body terminal insertion point is always endIndex - 1
                insert_index = max(1, end_index - 1)

            # 3. Format appended content with optional newline
            content_to_insert = input_data.content
            if input_data.addNewline and not content_to_insert.startswith("\n"):
                content_to_insert = "\n" + content_to_insert

            # 4. Execute atomic batchUpdate InsertTextRequest
            requests = [
                {
                    "insertText": {
                        "location": {
                            "index": insert_index
                        },
                        "text": content_to_insert
                    }
                }
            ]

            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()

            logger.info(f"Successfully appended {len(content_to_insert)} characters to Google Doc '{doc_id}' at index {insert_index}")

            return {
                "success": True,
                "documentId": doc_id,
                "appendedCharacters": len(content_to_insert),
                "insertLocationIndex": insert_index,
                "message": "Content appended successfully to Google Doc."
            }

        except HttpError as e:
            logger.error(f"Google Docs API error: {e}")
            if e.resp.status == 401:
                raise MCPError(ErrorCode.AUTHENTICATION_REQUIRED, "Google authentication expired or invalid.")
            elif e.resp.status == 429:
                raise MCPError(ErrorCode.RATE_LIMIT_EXCEEDED, "Google Docs API rate limit exceeded.")
            else:
                raise MCPError(ErrorCode.UPSTREAM_API_ERROR, f"Google Docs API error: {e.reason}")
        except MCPError:
            raise
        except Exception as e:
            logger.error(f"Internal error in append_content: {e}")
            raise MCPError(ErrorCode.INTERNAL_ERROR, str(e))
