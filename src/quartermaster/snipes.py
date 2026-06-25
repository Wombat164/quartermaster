"""Snipe lifecycle service: create (reserve + insert) and transition (validate the edge
+ release budget on leaving a holding state). Everything runs inside the caller's
session transaction, so the budget release and the state change commit together
(plan sec.3: release in the SAME transaction).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from . import ledger
from .fsm import State, can_transition, releases_budget
from .models import Snipe, Source


class IllegalTransition(Exception):
    pass


def create_snipe(
    session: Session,
    *,
    account: str,
    ebay_item_id: str,
    snapshot_hash: str,
    source: Source,
    reserved_cents: int,
    budget_id: int = 1,
) -> Snipe:
    """Reserve budget, then write the PENDING snipe -- atomic within the session."""
    ledger.reserve(session, budget_id, reserved_cents)
    snipe = Snipe(
        account=account,
        ebay_item_id=ebay_item_id,
        snapshot_hash=snapshot_hash,
        source=source,
        state=State.PENDING,
        reserved_cents=reserved_cents,
    )
    session.add(snipe)
    session.flush()
    return snipe


def transition(session: Session, snipe: Snipe, to: State, budget_id: int = 1) -> None:
    src = snipe.state
    if not can_transition(src, to):
        raise IllegalTransition(f"{src} -> {to} is not an allowed transition")
    if releases_budget(src, to):
        ledger.release(session, budget_id, snipe.reserved_cents)
    snipe.state = to
    session.flush()
