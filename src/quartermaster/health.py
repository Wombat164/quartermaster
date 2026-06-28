"""healthchecks.io dead-man's-switch ping (plan sec.5 / sec.8).

A best-effort GET to the configured ping URL at the END of a successful run. If a scheduled run
stops (crash, hang, host down), healthchecks.io stops receiving pings and alerts. Optional -- only
pings when `QM_HEALTHCHECKS_PING_URL` is set -- and a failed ping never crashes the run.
"""

from __future__ import annotations

import httpx


def ping(url: str, *, client: httpx.Client | None = None, timeout: float = 10.0) -> bool:
    """GET the healthchecks ping URL. True on success; False on any error (never raises)."""
    owns_client = client is None
    http = client if client is not None else httpx.Client(timeout=timeout)
    try:
        return http.get(url).is_success
    except httpx.HTTPError:
        return False
    finally:
        if owns_client:
            http.close()
