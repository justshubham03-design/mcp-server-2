import os
import json
from pathlib import Path
from typing import Optional, List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from ..utils.errors import MCPError, ErrorCode
from ..utils.logger import get_sanitized_logger

logger = get_sanitized_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/documents"
]

class GoogleAuthManager:
    """Manages Google OAuth 2.0 lifecycle, token persistence, and automatic refresh."""
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        token_path: Optional[str] = None
    ):
        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth2callback")
        
        default_token_path = os.path.expanduser("~/.config/google-mcp/token.json")
        self.token_path = token_path or os.getenv("GOOGLE_TOKEN_PATH") or default_token_path

    def get_credentials(self, allow_interactive: bool = False) -> Credentials:
        """
        Retrieves valid Google OAuth2 credentials.
        Reuses stored token if valid; refreshes token if expired; launches flow if interactive.
        """
        creds: Optional[Credentials] = None

        # 1. Check direct environment variable string / base64 (Ideal for cloud/Railway deployments)
        token_json_env = os.getenv("GOOGLE_TOKEN_JSON")
        token_b64_env = os.getenv("GOOGLE_TOKEN_BASE64")
        if token_b64_env and not token_json_env:
            import base64
            try:
                token_json_env = base64.b64decode(token_b64_env).decode("utf-8")
            except Exception as e:
                logger.warning(f"Failed to decode GOOGLE_TOKEN_BASE64: {e}")

        if token_json_env:
            try:
                token_info = json.loads(token_json_env)
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            except Exception as e:
                logger.warning(f"Failed to load credentials from GOOGLE_TOKEN_JSON: {e}")

        # 2. Check existing token file across possible locations
        if not creds:
            possible_paths = [
                Path(self.token_path),
                Path(__file__).resolve().parent.parent.parent.parent / self.token_path,
                Path("./.config/google_token.json").resolve(),
                Path(".config/google_token.json"),
                Path.home() / ".config" / "google-mcp" / "token.json"
            ]
            for p in possible_paths:
                if p.exists() and p.is_file():
                    try:
                        creds = Credentials.from_authorized_user_file(str(p), SCOPES)
                        self.token_path = str(p)
                        logger.info(f"Loaded valid Google OAuth token from {p}")
                        break
                    except Exception as e:
                        logger.warning(f"Failed to read existing token file at {p}: {e}")

        # 2. Check validity and refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Access token expired. Refreshing using stored refresh_token...")
                creds.refresh(Request())
                self._save_credentials(creds)
                logger.info("Successfully refreshed Google OAuth credentials.")
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
                creds = None

        # 3. If valid, return
        if creds and creds.valid:
            return creds

        # 4. If invalid/missing and interactive allowed
        if allow_interactive:
            return self.authenticate_interactive()

        raise MCPError(
            ErrorCode.AUTHENTICATION_REQUIRED,
            "Google authentication is required. Please set valid OAuth credentials or run authentication flow."
        )

    def authenticate_interactive(self) -> Credentials:
        """Launches interactive local web server OAuth flow."""
        if not self.client_id or not self.client_secret:
            raise MCPError(
                ErrorCode.AUTHENTICATION_REQUIRED,
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required to initiate authentication."
            )

        redirect_uris = list(set([self.redirect_uri, "http://localhost", "http://localhost:3000/oauth2callback"]))
        client_config = {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": redirect_uris
            }
        }

        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
        self._save_credentials(creds)
        logger.info(f"OAuth credentials saved successfully to {self.token_path}")
        return creds

    def _save_credentials(self, creds: Credentials):
        """Saves credentials safely with restricted user permissions."""
        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        with open(self.token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        try:
            os.chmod(self.token_path, 0o600)
        except Exception:
            pass
