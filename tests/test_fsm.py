"""FSM structure + the budget-holding/release classification."""

from __future__ import annotations

from quartermaster.fsm import (
    ALLOWED,
    HOLDING,
    TERMINAL,
    State,
    can_transition,
    releases_budget,
)


def test_every_state_is_classified() -> None:
    for state in State:
        assert state in ALLOWED  # no state without an (possibly empty) edge set


def test_terminal_states_have_no_outgoing_edges() -> None:
    for state in TERMINAL:
        assert ALLOWED[state] == frozenset()


def test_terminal_states_are_not_holding() -> None:
    assert TERMINAL.isdisjoint(HOLDING)


def test_allowed_targets_are_real_states() -> None:
    for targets in ALLOWED.values():
        for dst in targets:
            assert isinstance(dst, State)


def test_can_transition() -> None:
    assert can_transition(State.PENDING, State.REGISTERED)
    assert not can_transition(State.PENDING, State.WON)
    assert not can_transition(State.KEPT, State.PENDING)  # terminal has no edges


def test_releases_only_on_leaving_holding() -> None:
    assert releases_budget(State.FIRED, State.LOST)  # losing terminal frees the hold
    assert releases_budget(State.WON, State.PAID)  # won settles -> released
    assert not releases_budget(State.FIRED, State.WON)  # still holding
    # fail-closed on money: moving to reconcile must NOT release
    assert not releases_budget(State.FIRED, State.NEEDS_HUMAN_RECONCILE)
