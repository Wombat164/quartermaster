"""Gmail API backend -- OPTIONAL (`pip install quartermaster[gmail]`).

For users who specifically want OAuth instead of an IMAP app-password. Read-only scope; the OAuth
client secret + token live under `data/` (gitignored), never committed. Fetches each message as raw
RFC822 and hands it to the shared `mail.parse_email` -- the SAME parser the file / stdin / IMAP
readers use. Not run in CI (needs real Google credentials + an interactive consent on first run).

Most adopters should NOT use this: the default file / stdin / IMAP readers need no Google Cloud
project and no extra dependency, and IMAP + an app-password covers Gmail too.

CAVEATS (Google-imposed -- documented so they don't bite silently): `gmail.readonly` is a Google
"restricted" scope, so an unverified personal app's refresh token EXPIRES AFTER ~7 DAYS (you re-
consent weekly) unless the app is verified (a CASA security audit); and the grant is whole-mailbox
read (Gmail has no per-label scope) -- use a dedicated forwarding account. This is why IMAP + an
app-password is the recommended live path.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .mail import parse_email
from .pipeline import RawListing

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def load_credentials(*, token_path: Path, client_secret_path: Path) -> Any:
    """Load read-only Gmail credentials, refreshing or running the consent flow as needed."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    scopes = [GMAIL_READONLY_SCOPE]
    creds = (
        Credentials.from_authorized_user_file(str(token_path), scopes)
        if token_path.exists()
        else None
    )
    if creds is None or not creds.valid:
        if creds is not None and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _label_id(service: Any, label: str) -> str | None:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for lab in labels:
        if lab.get("name") == label:
            return str(lab.get("id"))
    return None


def read_label(label: str, *, token_path: Path, client_secret_path: Path) -> list[RawListing]:
    """Read-only: fetch every message under `label` as raw RFC822 -> the shared parser."""
    from googleapiclient.discovery import build

    creds = load_credentials(token_path=token_path, client_secret_path=client_secret_path)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    label_id = _label_id(service, label)
    if label_id is None:
        return []
    listed = service.users().messages().list(userId="me", labelIds=[label_id]).execute()
    ids = [m["id"] for m in listed.get("messages", [])]
    out: list[RawListing] = []
    for i in ids:
        msg = service.users().messages().get(userId="me", id=i, format="raw").execute()
        out.append(parse_email(base64.urlsafe_b64decode(msg["raw"])))
    return out
