# Decisions

Lightweight decision log. Plan-affecting or plan-extending choices go here so code and
`docs/plan-final.md` never drift. Newest first.

## 2026-06-26 -- v0 increment 3: CI + network-egress blocker (the safety net)

- GitHub Actions `.github/workflows/ci.yml`: `uv sync --locked` (lock-drift gate) ->
  ruff check -> ruff format --check -> mypy --strict -> pytest -> bandit (src) ->
  pip-audit, plus a separate gitleaks job. Runs on main + dev + PRs.
- **AUTOUSE network-egress blocker** (`conftest.block_network`): patches
  `socket.connect` / `socket.create_connection` to raise `NetworkBlocked` on any
  non-loopback host, so NO test can ever reach eBay / Gixen / SerpApi / a classifieds
  inbox or place a real bid. Loopback passes through (SQLite uses no socket, so the DB
  tests are unaffected). Verified by `test_egress` (external blocked; loopback reaches
  the OS error, not NetworkBlocked).
- Ran `ruff format` across the tree (consistent style; the CI format gate is green).
- 19 tests pass; ruff + mypy --strict + bandit clean; pip-audit reports no CVEs.

## 2026-06-25 -- v0 increment 2: schema core (ledger + FSM + source-tag)

Tier-A money/safety -> full rigor (plan sec.9).
- Models (money as integer CENTS, never float): `Budget` (singleton; CHECK
  0 <= committed <= cap) + `Snipe` (source immutable via `@validates`; idempotency
  `UNIQUE(account, ebay_item_id, snapshot_hash)`; UTC-aware timestamps via a
  `UTCDateTime` TypeDecorator since SQLite has no native tz).
- Reserved-budget ledger (sec.3 CRIT fix): atomic `reserve` (guarded UPDATE, refuses to
  exceed cap), guarded `release` (refuses underflow), `reconcile` (recomputes
  committed = sum(reserved over HOLDING snipes) -- the leak detector).
- FSM (sec.5): hand-rolled enum + transition table. **DEVIATION** from `python-statemachine`
  (sec.6): chosen for transparency + property-testability of the money invariant; can be
  wrapped later without changing the table. The HOLDING set drives release -- a reservation
  frees exactly when a snipe LEAVES holding; `NEEDS_HUMAN_RECONCILE` stays holding
  (fail-closed on money).
- `snipes` service: `create` (reserve + insert) and `transition` (validate edge + release)
  run in the caller's session transaction (release in the SAME tx as the state change).
- SQLite WAL + busy_timeout + foreign_keys via a connect listener.
- Alembic initial migration (reversible); custom-type import wired into the env mako
  template so future autogen does not break.
- Tests (17 pass): a hypothesis STATEFUL property test (committed == sum(holding reserved)
  and 0 <= committed <= cap across random create/transition sequences) + reserve/release/
  reconcile units + FSM + source-immutability + idempotency + migration
  upgrade -> downgrade -> upgrade. Still NO bidding/LLM/eBay/SPD-DB.

## 2026-06-25 -- v0 increment 1: toolchain + skeleton

- uv project (src-layout, hatchling build); dev extras: ruff, mypy (strict), pytest
  (+asyncio, cov), respx, hypothesis, bandit, pip-audit, pre-commit. `uv.lock`
  committed (reproducible builds, plan sec.9).
- ruff lint selects S (security), DTZ (no-naive-datetime -> the plan's tz-aware-UTC
  rule), ASYNC, B, I, UP, E/F, RUF. mypy strict on src + tests.
- pre-commit: ruff + ruff-format + mypy + gitleaks (gitleaks mandatory, plan sec.4).
- **DEVIATION:** Python PINNED to 3.13 via a COMMITTED `.python-version` (un-ignored it
  in `.gitignore`). Reason: plan sec.6 chose 3.13, and the later scientific/ML deps
  (numpy/scipy/llm-guard) may lack 3.14 wheels; `>=3.13` alone let uv pick 3.14.
  `requires-python` stays `>=3.13`.
- No runtime deps yet (v0 foundation); deps are added per functional block as v1 lands.
- Validated: ruff clean, mypy strict clean, pytest green on 3.13.14.

## 2026-06-25 -- Architecture + UX artifacts distilled from plan-final

- `docs/architecture.md` + `docs/ux-mock.md` make `plan-final.md` concrete (they double
  as the eBay-application "data flows + mocks" artifacts). No plan changes -- pure
  distillation of the authoritative plan.
- **UX channel model:** digest = OUTBOUND, batched daily; approval = OUT-OF-BAND signed
  token, distinct from the attacker-influenceable classifieds inbound inbox; critical
  push reserved for time-critical, verified, EU items only. (Implements trust boundary
  B2 + anti-alert-fatigue.)
- **Anti-confirmation-fatigue:** only verified + EU + costs-known items get an APPROVE
  button; everything else is ALERT-ONLY (no button). Type-to-confirm friction scales
  with spend above a threshold. *(Threshold value = OPEN; see ux-mock open questions.)*
- **Confidence/provenance per row:** badge (VERIFIED/UNVERIFIED/BOOTSTRAP) + comps
  state/N + source tag + landed-cost breakdown, per decision-support best practice.
- Open UX questions tracked in `docs/ux-mock.md` (digest surface, friction threshold,
  push channel, progressive disclosure) -- resolve before/at v1.
