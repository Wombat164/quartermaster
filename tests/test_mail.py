"""Provider-agnostic email input: stdlib RFC822 parsing + the file/stdin/mbox readers."""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from quartermaster import mail

PLAIN_EML = (
    b"Subject: RAM kit alert\n"
    b"From: alerts@2dehands.be\n"
    b"Content-Type: text/plain; charset=utf-8\n"
    b"\n"
    b"Corsair 2x16GB DDR4 EUR 80\n"
    b"https://2dehands.be/x\n"
)


def test_parse_plaintext_eml() -> None:
    raw = mail.parse_email(PLAIN_EML)
    assert raw.title == "RAM kit alert"
    assert "Corsair 2x16GB DDR4 EUR 80" in raw.text
    assert raw.url == "https://2dehands.be/x"


def test_parse_multipart_prefers_plaintext() -> None:
    eml = (
        b"Subject: alert\n"
        b'Content-Type: multipart/alternative; boundary="b"\n\n'
        b"--b\nContent-Type: text/plain\n\nplain 16GB DDR4\n"
        b"--b\nContent-Type: text/html\n\n<p>html 16GB</p>\n--b--\n"
    )
    assert "plain 16GB DDR4" in mail.parse_email(eml).text


def test_parse_html_fallback_strips_tags() -> None:
    eml = b"Subject: a\nContent-Type: text/html\n\n<p>Crucial <b>32GB</b> DDR4</p>\n"
    raw = mail.parse_email(eml)
    assert "Crucial" in raw.text
    assert "32GB" in raw.text
    assert "<" not in raw.text


def test_read_path_eml_and_txt(tmp_path: Path) -> None:
    (tmp_path / "a.eml").write_bytes(PLAIN_EML)
    (tmp_path / "b.txt").write_text("Crucial 16GB DDR4 EUR 30", encoding="utf-8")
    raws = mail.read_path(tmp_path)
    assert len(raws) == 2
    bodies = " ".join(r.text for r in raws)
    assert "Corsair 2x16GB DDR4" in bodies  # the .eml was parsed
    assert "Crucial 16GB DDR4" in bodies  # the .txt is a bare body


def test_read_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=io.BytesIO(PLAIN_EML)))
    raws = mail.read_stdin()
    assert len(raws) == 1
    assert "Corsair" in raws[0].text


def test_read_mbox(tmp_path: Path) -> None:
    box = tmp_path / "alerts.mbox"
    box.write_bytes(b"From alerts Thu Jan  1 00:00:00 2026\n" + PLAIN_EML + b"\n")
    raws = mail.read_mbox(box)
    assert len(raws) == 1
    assert "Corsair" in raws[0].text
