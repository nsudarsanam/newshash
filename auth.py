"""Gmail OAuth2 authentication."""

import os
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path("token.json")
CREDENTIALS_PATH = Path(os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json"))


def _run_auth_flow() -> Credentials:
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Gmail credentials file not found at '{CREDENTIALS_PATH}'.\n"
            "Download it from Google Cloud Console > APIs & Services > Credentials.\n"
            "Set GMAIL_CREDENTIALS_FILE env var to point to it if it's elsewhere."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    return flow.run_local_server(port=0)


def get_gmail_service():
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Refresh token has been revoked or expired — delete the stale
                # token and re-authenticate interactively.
                TOKEN_PATH.unlink(missing_ok=True)
                creds = _run_auth_flow()
        else:
            creds = _run_auth_flow()

        TOKEN_PATH.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)
