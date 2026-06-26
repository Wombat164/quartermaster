"""Keystone: a stateful property test proving the reserved-budget ledger never leaks
and never exceeds the cap across arbitrary create/transition sequences -- plus targeted
unit tests for reserve / release / reconcile and the transition guard.
"""

from __future__ import annotations

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from sqlalchemy import update
from sqlalchemy.orm import Session

from quartermaster import ledger, snipes
from quartermaster.db import Base, make_engine, make_session_factory
from quartermaster.fsm import ALLOWED, HOLDING, State
from quartermaster.ledger import BudgetExceeded
from quartermaster.models import Budget, Snipe, Source
from quartermaster.snipes import IllegalTransition

CAP = 100_000


@settings(max_examples=40, stateful_step_count=25)
class LedgerStateMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.engine = make_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session: Session = make_session_factory(self.engine)()
        self.session.add(Budget(id=1, cap_cents=CAP, committed_cents=0))
        self.session.flush()
        self.model: dict[int, tuple[State, int]] = {}
        self.n = 0

    def _model_committed(self) -> int:
        return sum(res for (state, res) in self.model.values() if state in HOLDING)

    @rule(amount=st.integers(min_value=0, max_value=CAP + 5000))
    def create(self, amount: int) -> None:
        self.n += 1
        before = self._model_committed()
        try:
            sn = snipes.create_snipe(
                self.session,
                account="a",
                ebay_item_id=f"i{self.n}",
                snapshot_hash="h",
                source=Source.EBAY_API,
                reserved_cents=amount,
            )
        except BudgetExceeded:
            assert before + amount > CAP
            return
        self.model[sn.id] = (State.PENDING, amount)

    @precondition(lambda self: bool(self.model))
    @rule(data=st.data())
    def transit(self, data: st.DataObject) -> None:
        sid = data.draw(st.sampled_from(sorted(self.model)))
        state, reserved = self.model[sid]
        targets = sorted(ALLOWED[state])
        if not targets:
            return
        to = data.draw(st.sampled_from(targets))
        sn = self.session.get(Snipe, sid)
        assert sn is not None
        snipes.transition(self.session, sn, to)
        self.model[sid] = (to, reserved)

    @invariant()
    def committed_never_leaks_or_exceeds(self) -> None:
        db = ledger.committed(self.session, 1)
        assert db == self._model_committed()
        assert 0 <= db <= CAP

    def teardown(self) -> None:
        self.session.close()
        self.engine.dispose()


TestLedgerProperty = LedgerStateMachine.TestCase


def _seed(session: Session, cents: int = 7100) -> Snipe:
    return snipes.create_snipe(
        session,
        account="a",
        ebay_item_id="i",
        snapshot_hash="h",
        source=Source.EBAY_API,
        reserved_cents=cents,
    )


def test_reserve_over_cap_raises_and_does_not_mutate(session: Session) -> None:
    with pytest.raises(BudgetExceeded):
        ledger.reserve(session, 1, CAP + 1)
    assert ledger.committed(session, 1) == 0


def test_release_underflow_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="underflow"):
        ledger.release(session, 1, 100)


def test_winning_cycle_holds_through_won_then_settles(session: Session) -> None:
    sn = _seed(session)
    assert ledger.committed(session, 1) == 7100
    for to in (State.REGISTERED, State.VERIFIED, State.FIRED, State.WON):
        snipes.transition(session, sn, to)
    assert ledger.committed(session, 1) == 7100  # still holding through WON
    snipes.transition(session, sn, State.PAID)  # settled -> released
    assert ledger.committed(session, 1) == 0


def test_reconcile_corrects_drift(session: Session) -> None:
    _seed(session)  # one HOLDING snipe, committed 7100
    session.execute(update(Budget).where(Budget.id == 1).values(committed_cents=999))
    assert ledger.reconcile(session, 1) == 7100
    assert ledger.committed(session, 1) == 7100


def test_illegal_transition_raises(session: Session) -> None:
    sn = _seed(session)
    with pytest.raises(IllegalTransition):
        snipes.transition(session, sn, State.WON)  # PENDING -> WON not allowed
