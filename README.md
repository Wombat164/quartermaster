# Quartermaster

![Quartermaster](assets/quartermaster-lockup.svg)

> **Codename: Quartermaster** · repo `deal-hunter-agent` · *Acquisitions, rationed.*

A personal agent that **finds the best value-for-fit RAM** (and later: any fitment-gated hardware) across eBay + EU classifieds, ranks it by live landed cost, and lets you **one-click approve** a Gixen auction snipe — within a hard budget.

Brand assets, palette & fonts: [`assets/BRAND.md`](assets/BRAND.md) · candidate domain **quartermaster.bid**.

> **Status:** 📐 Planning complete, **no code yet.** This repo currently holds the hardened design produced through two adversarial red-team passes + OSS research. Implementation starts at **v0** (see the roadmap in the plan).

---

## 🚦 READ THIS FIRST — Gate 0 (go/no-go before any code)

The entire eBay leg depends on getting **eBay production Browse API access**, which is a *gated* "restricted" API and may be **denied** for a personal sniping app. **Open an eBay Developer Support ticket** (personal use, human-approved, no AI on eBay content, <6h purge) and get a written yes/no **before building the eBay leg.**
- **Yes →** build v0 → v1 → v2.
- **No →** fall back to classifieds-only (thin) or manual Gixen + native saved-search alerts.

## The non-negotiables (compliance & safety — hard-coded)
1. **Human one-click approval before every binding bid** (eBay's Feb-2026 UA bans autonomous order flows). Gixen still fires the pre-approved max unattended at close.
2. **eBay content is processed deterministically — never sent to an LLM**; raw eBay content purged **< 6 h**; immutable `source` tag enforced by test.
3. **No scraping. Classifieds = native saved-search alert EMAILS only** (the email body *is* the dataset; no re-resolve/fetch). Images excluded from the LLM path.
4. **EU-only auto-bid**; fail-closed kill-switch + `DRY_RUN` default-true; arming real money needs two independent signals.
5. **Reserved-budget ledger with a release path** (Σ live max-bids ≤ cap, released on every terminal state).

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

*Private repo — personal use only. See plan §2/§11 for GDPR & ToS constraints.*
