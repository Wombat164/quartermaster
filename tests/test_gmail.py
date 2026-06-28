"""Gmail reader: the pure message-parsing core (text/plain, multipart, HTML fallback, subject,
url). The OAuth + API wiring needs real credentials and is not exercised here."""

from __future__ import annotations

import base64

from quartermaster.gmail import message_to_raw, read_messages


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _msg(payload: dict[str, object]) -> dict[str, object]:
    return {"payload": payload}


def test_plaintext_message() -> None:
    raw = message_to_raw(
        _msg(
            {
                "mimeType": "text/plain",
                "headers": [{"name": "Subject", "value": "RAM kit alert"}],
                "body": {"data": _b64("Corsair 2x16GB DDR4 EUR 80\nhttps://2dehands.be/x")},
            }
        )
    )
    assert raw.title == "RAM kit alert"
    assert "Corsair 2x16GB DDR4 EUR 80" in raw.text
    assert raw.url == "https://2dehands.be/x"


def test_multipart_prefers_plaintext() -> None:
    raw = message_to_raw(
        _msg(
            {
                "mimeType": "multipart/alternative",
                "headers": [{"name": "Subject", "value": "alert"}],
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64("plain 16GB DDR4")}},
                    {"mimeType": "text/html", "body": {"data": _b64("<p>html 16GB</p>")}},
                ],
            }
        )
    )
    assert raw.text == "plain 16GB DDR4"


def test_html_fallback_strips_tags() -> None:
    raw = message_to_raw(
        _msg(
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/html",
                        "body": {"data": _b64("<p>Crucial <b>32GB</b> DDR4</p>")},
                    }
                ],
            }
        )
    )
    assert "Crucial" in raw.text
    assert "32GB" in raw.text
    assert "<" not in raw.text


def test_missing_payload_is_empty() -> None:
    raw = message_to_raw({})
    assert raw.text == ""
    assert raw.title == ""
    assert raw.url == ""


def test_read_messages_maps_all() -> None:
    msgs: list[dict[str, object]] = [
        _msg({"mimeType": "text/plain", "body": {"data": _b64(f"16GB DDR4 #{i}")}})
        for i in range(3)
    ]
    raws = read_messages(msgs)
    assert len(raws) == 3
    assert all("DDR4" in r.text for r in raws)
