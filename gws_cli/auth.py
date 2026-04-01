"""OAuth2 authentication for Google Workspace APIs."""

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/documents",
]

CONFIG_DIR = Path.home() / ".config" / "gws-cli"
TOKEN_PATH = CONFIG_DIR / "token.json"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"


def get_credentials() -> Credentials:
    """Get valid user credentials, refreshing or initiating OAuth flow as needed."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"OAuth credentials not found at {CREDENTIALS_PATH}\n"
                    "Download your OAuth client credentials from Google Cloud Console:\n"
                    "  1. Go to https://console.cloud.google.com/apis/credentials\n"
                    "  2. Create an OAuth 2.0 Client ID (Desktop app)\n"
                    "  3. Download the JSON and save it to:\n"
                    f"     {CREDENTIALS_PATH}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def build_service(api: str, version: str):
    """Build a Google API service client."""
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build(api, version, credentials=creds)


def logout():
    """Remove stored credentials."""
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        return True
    return False
