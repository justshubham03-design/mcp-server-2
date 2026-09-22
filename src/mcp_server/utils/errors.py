from enum import Enum
from typing import Optional, Dict, Any

class ErrorCode(str, Enum):
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    UPSTREAM_API_ERROR = "UPSTREAM_API_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class MCPError(Exception):
    """Base exception for all MCP Server errors with typed codes and sanitized messages."""
    def __init__(self, code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": False,
            "error": {
                "code": self.code.value,
                "message": self.message,
                **({"details": self.details} if self.details else {})
            }
        }
