"""Provider-agnostic email input -- the default needs no account, no keys, no extra deps.

A `RawListing` producer for the funnel. The PARSE is stdlib `email` (RFC822); the SOURCES are all
stdlib too:
- files: a directory of `.eml` (or a single file / bare-body `.txt`) -- ZERO setup;
- an `.mbox` (every mail client can export one);
- one message on stdin (so anything -- incl. an LLM agent with a Gmail MCP -- can pipe to us);
- IMAP via stdlib `imaplib`: works with ANY provider (Gmail app-password, Outlook, Fastmail, Proton
  Bridge, self-hosted) with no third-party dependency.

The Gmail API (OAuth) lives in `gmail.py` behind the optional `[gmail]` extra, for users who insist
on OAuth; almost nobody needs it -- IMAP + an app-password covers Gmail too.
"""

from __future__ import annotations

import email
import imaplib
import mailbox
import re
import sys
from collections.abc import Iterable
from email.message import EmailMessage
from email.policy import default as default_policy
from pathlib import Path

from .pipeline import RawListing

_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+")


def _first_url(text: str) -> str:
    m = _URL_RE.search(text)
    return m.group(0) if m else ""


def _body(msg: EmailMessage) -> str:
    """Best-effort plain text: prefer text/plain, fall back to stripped text/html."""
    if msg.is_multipart():
        plain = msg.get_body(preferencelist=("plain",))
        if plain is not None:
            return str(plain.get_content())
        html = msg.get_body(preferencelist=("html",))
        return _TAG_RE.sub(" ", str(html.get_content())) if html is not None else ""
    text = str(msg.get_content())
    return _TAG_RE.sub(" ", text) if msg.get_content_type() == "text/html" else text


def parse_email(raw: bytes) -> RawListing:
    """Parse RFC822 bytes into a RawListing (body text, subject title, first link). Total."""
    msg: EmailMessage = email.message_from_bytes(raw, policy=default_policy)
    text = _body(msg)
    return RawListing(text=text, title=str(msg.get("Subject", "") or ""), url=_first_url(text))


# --- sources (all stdlib; each yields RawListings) ---


def _read_file(p: Path) -> RawListing:
    # .eml -> full RFC822 parse; anything else (.txt, ...) -> the file IS the bare body.
    if p.suffix.lower() == ".eml":
        return parse_email(p.read_bytes())
    return RawListing(text=p.read_text(encoding="utf-8", errors="replace"))


def read_path(path: Path) -> list[RawListing]:
    """Every file under `path` (dir or single file); `.eml` -> email parse, else a bare body."""
    files = sorted(path.iterdir()) if path.is_dir() else [path]
    return [_read_file(p) for p in files if p.is_file()]


def read_paths(paths: Iterable[Path]) -> list[RawListing]:
    out: list[RawListing] = []
    for p in paths:
        out.extend(read_path(p))
    return out


def read_mbox(path: Path) -> list[RawListing]:
    box = mailbox.mbox(str(path))
    try:
        return [parse_email(msg.as_bytes()) for msg in box]
    finally:
        box.close()


def read_stdin() -> list[RawListing]:
    return [parse_email(sys.stdin.buffer.read())]


def read_imap(*, host: str, port: int, user: str, password: str, folder: str) -> list[RawListing]:
    """Read-only IMAP fetch of every message in `folder`. Provider-agnostic, stdlib only."""
    out: list[RawListing] = []
    with imaplib.IMAP4_SSL(host, port) as imap:
        imap.login(user, password)
        imap.select(folder, readonly=True)
        _typ, data = imap.search(None, "ALL")
        ids = data[0].split() if data and data[0] else []
        for mid in ids:
            _typ, msg_data = imap.fetch(mid, "(RFC822)")
            raw = msg_data[0][1] if msg_data and isinstance(msg_data[0], tuple) else None
            if isinstance(raw, bytes):
                out.append(parse_email(raw))
    return out
