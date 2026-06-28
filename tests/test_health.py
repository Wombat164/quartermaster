"""healthchecks ping: best-effort, swallows errors, never raises. respx-mocked (no live call)."""

from __future__ import annotations

import httpx
import respx

from quartermaster.health import ping

URL = "https://hc-ping.com/abc"


@respx.mock
def test_ping_success() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200))
    assert ping(URL) is True
    assert route.called


@respx.mock
def test_ping_failure_status_is_false() -> None:
    respx.get(URL).mock(return_value=httpx.Response(500))
    assert ping(URL) is False


@respx.mock
def test_ping_network_error_is_swallowed() -> None:
    respx.get(URL).mock(side_effect=httpx.ConnectError("down"))
    assert ping(URL) is False  # never raises
