import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from ..utils.errors import MCPError, ErrorCode

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

def validate_email_address(email: str) -> str:
    cleaned = email.strip()
    # Check for display name format e.g. "John Doe <john@example.com>"
    match = re.search(r'<([^>]+)>', cleaned)
    addr_to_check = match.group(1) if match else cleaned
    if not EMAIL_REGEX.match(addr_to_check):
        raise MCPError(ErrorCode.INVALID_RECIPIENT, f"Invalid email recipient format: '{email}'")
    return cleaned

class GmailCreateDraftInput(BaseModel):
    to: List[str] = Field(..., min_length=1, description="List of recipient email addresses (at least one required)")
    cc: Optional[List[str]] = Field(default_factory=list, description="Optional CC recipient email addresses")
    bcc: Optional[List[str]] = Field(default_factory=list, description="Optional BCC recipient email addresses")
    subject: str = Field(..., min_length=1, description="Subject line of the email")
    body: str = Field(..., min_length=1, description="Body content of the email (plain text)")

    @field_validator("to", "cc", "bcc")
    @classmethod
    def check_emails(cls, emails: Optional[List[str]]) -> List[str]:
        if not emails:
            return []
        validated = []
        for e in emails:
            if e and e.strip():
                validated.append(validate_email_address(e))
        return validated

class GmailSendEmailInput(BaseModel):
    to: List[str] = Field(..., min_length=1, description="List of recipient email addresses (at least one required)")
    cc: Optional[List[str]] = Field(default_factory=list, description="Optional CC recipient email addresses")
    bcc: Optional[List[str]] = Field(default_factory=list, description="Optional BCC recipient email addresses")
    subject: str = Field(..., min_length=1, description="Subject line of the email")
    body: str = Field(..., min_length=1, description="Body content of the email (plain text)")

    @field_validator("to", "cc", "bcc")
    @classmethod
    def check_emails(cls, emails: Optional[List[str]]) -> List[str]:
        if not emails:
            return []
        validated = []
        for e in emails:
            if e and e.strip():
                validated.append(validate_email_address(e))
        return validated

class GoogleDocsAppendInput(BaseModel):
    documentId: str = Field(..., min_length=1, description="The ID of the target Google Doc")
    content: str = Field(..., min_length=1, description="Text content to append to the end of the document")
    addNewline: Optional[bool] = Field(default=True, description="Whether to ensure content begins on a new line")
