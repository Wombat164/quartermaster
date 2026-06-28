# Quartermaster

![Quartermaster](assets/quartermaster-lockup.svg)

[![ci](https://github.com/Wombat164/quartermaster/actions/workflows/ci.yml/badge.svg)](https://github.com/Wombat164/quartermaster/actions/workflows/ci.yml) · MIT · Python 3.13+ · a personal project, provided as-is (issues welcome, no support guarantee)

> **Codename: Quartermaster** · repo `quartermaster` · *Acquisitions, rationed.*

A personal agent that **finds the best value-for-fit RAM** (and later: any fitment-gated hardware) across EU classifieds + multi-retailer price data, and ranks it by **live landed cost vs the market** -- so you see the best deal available now. Buying stays in your hands: a one-click-approved Gixen auction snipe within a hard budget is a **later phase (Phase 2)**.

**Docs site:** <https://wombat164.github.io/quartermaster/> · Brand assets, palette & fonts: [`assets/BRAND.md`](assets/BRAND.md) · candidate domain **quartermaster.bid**.

> **Status (2026-06-28):** **Public + MIT.** Phase-1 pipeline runnable end-to-end (fitment -> valuation/ECB-FX -> live/bootstrap baseline -> deal% -> ranked digest), with provider-agnostic email input (file / stdin / IMAP; Gmail optional). 212 tests green. **Phase 1 = SEARCH + COMPARE**; bid/buy is Phase 2 (Gate 0: eBay API dropped). See [`DECISIONS.md`](DECISIONS.md).

## Quickstart

Requires **Python 3.13+**. It is **not on PyPI** -- install from this repo. (The unrelated `quartermaster` package on PyPI is *not* this project; don't `pip install quartermaster`.)

```sh
# zero-install run (uv fetches Python 3.13 for you) against the bundled sample:
uvx --from git+https://github.com/Wombat164/quartermaster.git quartermaster examples/sample-alert.eml

# or put the CLI on PATH:
uv tool install git+https://github.com/Wombat164/quartermaster.git
quartermaster examples/sample-alert.eml              # bundled sample  ->  a ranked digest
quartermaster path/to/your/alerts/*.eml              # your own .eml / .txt files
cat alert.eml | QM_MAIL_SOURCE=stdin quartermaster   # or pipe one in
```

(`pipx install --python 3.13 git+...`, or `pip install git+https://github.com/Wombat164/quartermaster.git` inside a 3.13 venv, also work.)

Runs alert-only with **zero accounts or keys** (deterministic regex extraction + a bootstrap price table). Opt in to more, each independent and off by default:

| Want | Set | Adds |
|---|---|---|
| LLM extraction (messy free-text listings) | `QM_ANTHROPIC_API_KEY` | Claude extraction (else regex-only) |
| Live market comps (real deal %) | `QM_SERPAPI_API_KEY` | SerpApi baseline (else a bootstrap table) |
| Live email from **any** provider | `QM_MAIL_SOURCE=imap` + `QM_IMAP_*` + an app-password | stdlib IMAP -- Gmail / Outlook / Fastmail / Proton / self-hosted |
| Gmail via OAuth (rarely needed) | the `[gmail]` extra (`uv tool install "quartermaster[gmail] @ git+https://github.com/Wombat164/quartermaster.git"`) + `QM_MAIL_SOURCE=gmail` | the Gmail API ([caveats](SECURITY.md) -- 7-day token, full-mailbox scope) |

Secrets come from your env / secret store (e.g. `export QM_SERPAPI_API_KEY=$(bw get password serpapi)`), never committed; `QM_DRY_RUN` defaults **true**. Copy [`.env.example`](.env.example) to `.env` to configure.

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
examples/sample-alert.eml       a bundled classifieds alert for the Quickstart
```

## Development

```sh
git clone https://github.com/Wombat164/quartermaster.git && cd quartermaster
uv sync --extra dev        # ruff + mypy-strict + pytest + bandit + pip-audit
uv run pytest              # 212 tests (incl. the golden-set quality gate)
```

The authoritative design is [`docs/plan-final.md`](docs/plan-final.md); every plan-affecting choice is logged newest-first in [`DECISIONS.md`](DECISIONS.md). Contributor guide: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Tech
Python 3.13 · `uv` · stdlib `email`/`imaplib` email input · `httpx` · Claude structured outputs + a dependency-light injection guard (llm-guard pluggable) · ECB FX via `currencyconverter` · SQLAlchemy 2 + Alembic · `structlog` (secret-redacted) + healthchecks.io · `respx` · GitHub Actions (ruff / mypy-strict / pytest + hypothesis / bandit / pip-audit / gitleaks; actions SHA-pinned). Phase-2 (bidding) adds the Gixen + reserved-budget-ledger machinery already built in v0.

Licensed **MIT** ([`LICENSE`](LICENSE)). Security model + private reporting: [`SECURITY.md`](SECURITY.md). Personal-use agent; see plan §2/§11 for GDPR & ToS constraints.
