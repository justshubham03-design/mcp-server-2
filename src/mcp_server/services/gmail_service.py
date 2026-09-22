import base64
from email.message import EmailMessage
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..auth.google_auth import GoogleAuthManager
from ..schemas.tool_schemas import GmailCreateDraftInput, GmailSendEmailInput
from ..utils.errors import MCPError, ErrorCode
from ..utils.logger import get_sanitized_logger

logger = get_sanitized_logger(__name__)

class GmailService:
    """Service wrapping Google Gmail API for creating drafts and sending emails."""
    def __init__(self, auth_manager: Optional[GoogleAuthManager] = None):
        self.auth_manager = auth_manager or GoogleAuthManager()

    def _get_service(self):
        creds = self.auth_manager.get_credentials()
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _build_mime_message(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> str:
        """Constructs an RFC 2822 MIME message and returns a Base64URL-encoded raw string."""
        msg = EmailMessage()
        msg.set_content(body, charset="utf-8")
        msg["Subject"] = subject
        msg["To"] = ", ".join(to)
        
        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)

        raw_bytes = msg.as_bytes()
        return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

    def create_draft(self, input_data: GmailCreateDraftInput) -> Dict[str, Any]:
        """Creates an email draft in Gmail without sending."""
        try:
            service = self._get_service()
            raw_message = self._build_mime_message(
                to=input_data.to,
                subject=input_data.subject,
                body=input_data.body,
                cc=input_data.cc,
                bcc=input_data.bcc
            )

            draft_body = {
                "message": {
                    "raw": raw_message
                }
            }

            resp = service.users().drafts().create(userId="me", body=draft_body).execute()
            draft_id = resp.get("id")
            message_id = resp.get("message", {}).get("id")
            logger.info(f"Successfully created Gmail draft. Draft ID: {draft_id}")

            return {
                "success": True,
                "draftId": draft_id,
                "messageId": message_id,
                "message": "Draft created successfully."
            }

        except HttpError as e:
            logger.error(f"Gmail API error during draft creation: {e}")
            if e.resp.status == 401:
                raise MCPError(ErrorCode.AUTHENTICATION_REQUIRED, "Google authentication expired or invalid.")
            elif e.resp.status == 429:
                raise MCPError(ErrorCode.RATE_LIMIT_EXCEEDED, "Gmail API rate limit exceeded.")
            else:
                raise MCPError(ErrorCode.UPSTREAM_API_ERROR, f"Gmail API error: {e.reason}")
        except MCPError:
            raise
        except Exception as e:
            logger.error(f"Internal error in create_draft: {e}")
            raise MCPError(ErrorCode.INTERNAL_ERROR, str(e))

    def send_email(self, input_data: GmailSendEmailInput) -> Dict[str, Any]:
        """Sends an email directly through the authenticated Gmail account."""
        try:
            service = self._get_service()
            raw_message = self._build_mime_message(
                to=input_data.to,
                subject=input_data.subject,
                body=input_data.body,
                cc=input_data.cc,
                bcc=input_data.bcc
            )

            send_body = {
                "raw": raw_message
            }

            resp = service.users().messages().send(userId="me", body=send_body).execute()
            message_id = resp.get("id")
            logger.info(f"Successfully sent email. Message ID: {message_id}")

            return {
                "success": True,
                "messageId": message_id,
                "recipientCount": len(input_data.to),
                "message": "Email sent successfully."
            }

        except HttpError as e:
            logger.error(f"Gmail API error during email sending: {e}")
            if e.resp.status == 401:
                raise MCPError(ErrorCode.AUTHENTICATION_REQUIRED, "Google authentication expired or invalid.")
            elif e.resp.status == 429:
                raise MCPError(ErrorCode.RATE_LIMIT_EXCEEDED, "Gmail API rate limit exceeded.")
            else:
                raise MCPError(ErrorCode.UPSTREAM_API_ERROR, f"Gmail API error: {e.reason}")
        except MCPError:
            raise
        except Exception as e:
            logger.error(f"Internal error in send_email: {e}")
            raise MCPError(ErrorCode.INTERNAL_ERROR, str(e))
