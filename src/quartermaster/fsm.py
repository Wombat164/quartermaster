"""Snipe finite-state machine (plan sec.5) + the budget-holding classification that
drives the reserved-budget ledger's release (plan sec.3 CRIT fix).

Hand-rolled (enum + transition table) on purpose: the money invariant -- a reservation
is released exactly when a snipe LEAVES a holding state -- must be transparent and
property-testable. python-statemachine can wrap this later without changing the table.
See DECISIONS.md.
"""

from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    PENDING = "PENDING"
    REGISTERED = "REGISTERED"
    VERIFIED = "VERIFIED"
    FIRED = "FIRED"
    WON = "WON"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    RECEIVED = "RECEIVED"
    TESTED = "TESTED"
    KEPT = "KEPT"
    RETURNED = "RETURNED"
    LOST = "LOST"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    NEEDS_HUMAN_RECONCILE = "NEEDS_HUMAN_RECONCILE"


# States that HOLD a budget reservation (money still owed or at risk). Leaving this set
# releases the reservation. NEEDS_HUMAN_RECONCILE stays holding -- fail-closed on money
# (a won-but-unrecorded snipe must NOT release budget; plan sec.3).
HOLDING: frozenset[State] = frozenset(
    {
        State.PENDING,
        State.REGISTERED,
        State.VERIFIED,
        State.FIRED,
        State.WON,
        State.NEEDS_HUMAN_RECONCILE,
    }
)

# Terminal states (no outgoing edges).
TERMINAL: frozenset[State] = frozenset(
    {State.KEPT, State.RETURNED, State.LOST, State.EXPIRED, State.CANCELLED, State.ERROR}
)

# Allowed edges. A reaper supplies the timeout edges to EXPIRED/ERROR; not modelled as
# auto-edges here. Terminal states map to an empty set.
ALLOWED: dict[State, frozenset[State]] = {
    State.PENDING: frozenset({State.REGISTERED, State.CANCELLED, State.ERROR, State.EXPIRED}),
    State.REGISTERED: frozenset({State.VERIFIED, State.CANCELLED, State.ERROR, State.EXPIRED}),
    State.VERIFIED: frozenset({State.FIRED, State.CANCELLED, State.ERROR, State.EXPIRED}),
    State.FIRED: frozenset({State.WON, State.LOST, State.ERROR, State.NEEDS_HUMAN_RECONCILE}),
    State.WON: frozenset({State.PAID, State.NEEDS_HUMAN_RECONCILE}),
    State.PAID: frozenset({State.SHIPPED}),
    State.SHIPPED: frozenset({State.RECEIVED}),
    State.RECEIVED: frozenset({State.TESTED}),
    State.TESTED: frozenset({State.KEPT, State.RETURNED}),
    State.NEEDS_HUMAN_RECONCILE: frozenset({State.PAID, State.LOST, State.CANCELLED, State.ERROR}),
    State.KEPT: frozenset(),
    State.RETURNED: frozenset(),
    State.LOST: frozenset(),
    State.EXPIRED: frozenset(),
    State.CANCELLED: frozenset(),
    State.ERROR: frozenset(),
}


def can_transition(src: State, dst: State) -> bool:
    return dst in ALLOWED.get(src, frozenset())


def is_holding(state: State) -> bool:
    return state in HOLDING


def releases_budget(src: State, dst: State) -> bool:
    """True iff src->dst frees the reservation (leaves the holding set)."""
    return src in HOLDING and dst not in HOLDING
