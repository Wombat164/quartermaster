"""Reserved-budget ledger (plan sec.3): atomic reserve, release, and a reconciler.

The CRIT invariant: committed_cents == sum(reserved_cents over HOLDING snipes), and
0 <= committed_cents <= cap_cents. reserve() refuses to exceed the cap atomically;
release() refuses to underflow; reconcile() recomputes from the snipe rows and corrects
drift (the leak detector). The old v2 bug was a ledger that never released -- here every
release is guarded and reconcile is the backstop.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from .fsm import HOLDING
from .models import Budget, Snipe


class BudgetExceeded(Exception):
    pass


def reserve(session: Session, budget_id: int, amount_cents: int) -> None:
    if amount_cents < 0:
        raise ValueError("amount_cents must be >= 0")
    res = cast(
        "CursorResult[Any]",
        session.execute(
            update(Budget)
            .where(
                Budget.id == budget_id,
                Budget.committed_cents + amount_cents <= Budget.cap_cents,
            )
            .values(committed_cents=Budget.committed_cents + amount_cents)
        ),
    )
    if res.rowcount != 1:
        raise BudgetExceeded(f"reserve {amount_cents} would exceed cap (budget {budget_id})")


def release(session: Session, budget_id: int, amount_cents: int) -> None:
    if amount_cents < 0:
        raise ValueError("amount_cents must be >= 0")
    res = cast(
        "CursorResult[Any]",
        session.execute(
            update(Budget)
            .where(Budget.id == budget_id, Budget.committed_cents - amount_cents >= 0)
            .values(committed_cents=Budget.committed_cents - amount_cents)
        ),
    )
    if res.rowcount != 1:
        raise ValueError(f"release {amount_cents} would underflow committed (budget {budget_id})")


def committed(session: Session, budget_id: int) -> int:
    val = session.scalar(select(Budget.committed_cents).where(Budget.id == budget_id))
    if val is None:
        raise ValueError(f"no budget {budget_id}")
    return val


def expected_committed(session: Session) -> int:
    """Sum of reservations over snipes still in a HOLDING state (the source of truth)."""
    total = session.scalar(
        select(func.coalesce(func.sum(Snipe.reserved_cents), 0)).where(
            Snipe.state.in_(tuple(HOLDING))
        )
    )
    return int(total or 0)


def reconcile(session: Session, budget_id: int) -> int:
    """Recompute committed from the holding snipes; correct drift. Returns the new value."""
    total = expected_committed(session)
    session.execute(update(Budget).where(Budget.id == budget_id).values(committed_cents=total))
    return total
