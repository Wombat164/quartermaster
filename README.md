# Quartermaster

![Quartermaster](assets/quartermaster-lockup.svg)

> **Codename: Quartermaster** · repo `quartermaster` · *Acquisitions, rationed.*

A personal agent that **finds the best value-for-fit RAM** (and later: any fitment-gated hardware) across EU classifieds + multi-retailer price data, and ranks it by **live landed cost vs the market** -- so you see the best deal available now. Buying stays in your hands: a one-click-approved Gixen auction snipe within a hard budget is a **later phase (Phase 2)**.

**Docs site:** <https://wombat164.github.io/quartermaster/> · Brand assets, palette & fonts: [`assets/BRAND.md`](assets/BRAND.md) · candidate domain **quartermaster.bid**.

> **Status (2026-06-27):** **Public + MIT.** v0 foundation + **P1.1 fitment core** shipped (toolchain, money/safety schema core, CI + egress blocker, the deterministic compatibility gate). **Phase 1 = SEARCH + COMPARE first**; bid/buy is Phase 2 (Gate 0: eBay API dropped). See [`DECISIONS.md`](DECISIONS.md).

---

## Gate 0 RESOLVED (2026-06-26) -- pivot to search + compare

Deep-research (`docs/background/ebay-gate0-research.md`) found production eBay Buy/Browse API access is partner-only, business-model-gated, "no guarantee", with no personal-app precedent -- too uncertain to build on. So the **eBay API is dropped**:
- **Phase 1 (now): SEARCH + COMPARE** on compliant sources -- classifieds saved-search alert EMAILS (discovery) + SerpApi Google Shopping as the compare baseline (retail / Amazon / eBay-as-price-comps, no scraping) + a bootstrap EUR/GB table. No approve button.
- **Phase 2 (deferred): BID/BUY** -- manual eBay + a Gixen snipe with one-click approval. The money/safety machinery (ledger/FSM/source-tag) is already built + tested in v0 increment 2.

## The non-negotiables (compliance & safety — hard-coded)
1. **Human one-click approval before every binding bid** (eBay's Feb-2026 UA bans autonomous order flows). Gixen still fires the pre-approved max unattended at close.
2. **eBay content is processed deterministically — never sent to an LLM**; raw eBay content purged **< 6 h**; immutable `source` tag enforced by test.
3. **No scraping. Classifieds = native saved-search alert EMAILS only** (the email body *is* the dataset; no re-resolve/fetch). Images excluded from the LLM path.
4. **EU-only auto-bid**; fail-closed kill-switch + `DRY_RUN` default-true; arming real money needs two independent signals.
5. **Reserved-budget ledger with a release path** (Σ live max-bids ≤ cap, released on every terminal state).

## Configuration & secrets

Config is separate from the program (12-factor). Everything runtime-tunable is an env var
prefixed `QM_` (or a gitignored `.env`) -- copy [`.env.example`](.env.example) to `.env` to start.
Secrets are `SecretStr` and live in your **secret store, injected via env** -- never committed:

```sh
export QM_SERPAPI_API_KEY="$(bw get password serpapi)"   # e.g. Bitwarden
```

`QM_DRY_RUN` defaults to **true** (fail-safe). Model: `src/quartermaster/config.py`; full
security posture: [`SECURITY.md`](SECURITY.md).

## Repo structure
```
docs/
  plan-final.md                 ← AUTHORITATIVE plan — start here
  history/
    plan-v2-hardened.md         consolidated plan (pre red-team #2)
    plan-v1-draft.md            first detailed draft (pre red-team #1)
    design-scaffold.md          original architecture scaffold + buy-vs-build
  background/
    ram-upgrade-guide.md        why this exists (the RAM the agent hunts)
    price-comparison-tools.md   price-API / MCP landscape research
PROMPT-FOR-RCDE.md              kickoff prompt for the implementing agent
```

## How to start
1. Read **`docs/plan-final.md`** end to end (it supersedes everything in `history/`).
2. Resolve **Gate 0** (eBay API access).
3. Build **v0 — thin foundation** (uv + ruff + mypy + pytest + Alembic schema + pydantic-settings/keyring + structlog + healthchecks ping + respx + network-egress test-blocker + `DECISIONS.md`). No business logic ships without a test + migration (for money/safety code) per the tiered DoD in §9.
4. Then **v1 — alert-only digest** (no bidding), then **v2 — approved snipe**.

## Tech (chosen in OSS research, see plan §6)
Python 3.13 · `uv` · `httpx`+`tenacity`+`pyrate-limiter` · Claude native structured outputs + `llm-guard` · `numpy`/`scipy.stats` + `CurrencyConverter` · Gixen `api.php` · `python-statemachine` · APScheduler 3.x + SQLAlchemy 2 + Alembic · `respx`+`vcrpy` · `structlog` + healthchecks.io · GitHub Actions (ruff/mypy/bandit/pip-audit/gitleaks).

Licensed **MIT** ([`LICENSE`](LICENSE)). Security model + private reporting: [`SECURITY.md`](SECURITY.md). Personal-use agent; see plan §2/§11 for GDPR & ToS constraints.
