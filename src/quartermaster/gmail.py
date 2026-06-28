"""Gmail one-label reader (P1.3c) -- read-only OAuth, classifieds alerts -> RawListings.

Two layers, mirroring the other adapters:
- the PURE core (`message_to_raw`, `read_messages`) parses a Gmail message resource (a dict) into a
  `RawListing` -- plaintext body (text/plain, else stripped text/html), the subject as title, the
  first link as url. Fully testable with fixture dicts, no API.
- the thin WIRING (`load_credentials`, `read_label`) does the read-only OAuth + the Gmail calls.
  Scope is `gmail.readonly`; the OAuth client secret + token live under `data/` (gitignored) and are
  never committed. Not exercised in CI (it needs real Google credentials + an interactive consent on
  first run; the saved token is reused after).
"""

from __future__ import annotations

import base64
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .pipeline import RawListing

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+")

# --- pure parsing core ---


def _str(v: object) -> str:
    return v if isinstance(v, str) else ""


def _header(payload: Mapping[str, object], name: str) -> str:
    headers = payload.get("headers")
    if isinstance(headers, list):
        for h in headers:
            if isinstance(h, Mapping) and _str(h.get("name")).lower() == name.lower():
                return _str(h.get("value"))
    return ""


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _body_text(part: Mapping[str, object]) -> str:
    body = part.get("body")
    data = body.get("data") if isinstance(body, Mapping) else None
    return _decode(data) if isinstance(data, str) else ""


def _extract_text(payload: Mapping[str, object]) -> str:
    if _str(payload.get("mimeType")) == "text/plain":
        text = _body_text(payload)
        if text:
            return text
    raw_parts = payload.get("parts")
    parts = [p for p in raw_parts if isinstance(p, Mapping)] if isinstance(raw_parts, list) else []
    for part in parts:  # prefer text/plain
        if _str(part.get("mimeType")) == "text/plain" and (text := _body_text(part)):
            return text
    for part in parts:  # fallback: HTML, tags stripped
        if _str(part.get("mimeType")) == "text/html" and (html := _body_text(part)):
            return _TAG_RE.sub(" ", html)
    for part in parts:  # nested multipart
        if nested := _extract_text(part):
            return nested
    return ""


def _first_url(text: str) -> str:
    m = _URL_RE.search(text)
    return m.group(0) if m else ""


def message_to_raw(message: Mapping[str, object]) -> RawListing:
    """Parse a Gmail message resource into a RawListing (body text, subject title, first link)."""
    raw_payload = message.get("payload")
    payload: Mapping[str, object] = raw_payload if isinstance(raw_payload, Mapping) else {}
    text = _extract_text(payload)
    return RawListing(text=text, title=_header(payload, "Subject"), url=_first_url(text))


def read_messages(messages: Iterable[Mapping[str, object]]) -> list[RawListing]:
    return [message_to_raw(m) for m in messages]


# --- thin OAuth + API wiring (needs real credentials; not run in CI) ---


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
    """Read-only: fetch every message under `label` and parse them into RawListings."""
    from googleapiclient.discovery import build

    creds = load_credentials(token_path=token_path, client_secret_path=client_secret_path)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    label_id = _label_id(service, label)
    if label_id is None:
        return []
    listed = service.users().messages().list(userId="me", labelIds=[label_id]).execute()
    ids = [m["id"] for m in listed.get("messages", [])]
    full = [service.users().messages().get(userId="me", id=i, format="full").execute() for i in ids]
    return read_messages(full)
