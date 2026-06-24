# Deal-Hunter Agent — Hardened Plan v2 (post red-team #1 + OSS research)
**Date:** 2026-06-24 · Supersedes v1. To be red-teamed again before finalizing.

## 0. The four reframes forced by red-team #1
1. **Legal → human-in-the-loop is mandatory.** eBay's 2026-02-20 User Agreement bans automated "data-gathering/extraction tools" and "any end-to-end flow that places orders without human review." Its API License also forbids feeding eBay content to an LLM and requires <6h purge. So: **no fully-autonomous eBay bidding.** Design = *auto-discover → auto-verify → auto-rank → one-click human approval → Gixen snipe.* (This overrides the earlier "full-auto" choice; full-auto eBay = account-ban risk. Full-auto remains possible only in the narrow, compliant sense of "Gixen fires the pre-approved max at close.")
2. **eBay content is processed deterministically — never by the LLM.** Regex/spec gates only; purge raw eBay content <6h; never send seller PII to Claude.
3. **Drop the classifieds scrapers entirely.** Marktplaats/2dehands/Kleinanzeigen/Leboncoin run DataDome/Akamai, ban + sue scrapers. Use ONLY native saved-search **email alerts** (Gmail, DKIM/SPF-verified) → re-resolve via official means. LLM free-text extraction applies to classifieds text only.
4. **Valuation must be live; budget must be reserved.** Static `market_ref` is fatal in the 2026 DRAM spike — use a rolling trimmed-median with a staleness gate. Global budget = a **reserved-commitment ledger** (Σ live max-bids ≤ cap), not a per-item check.

## 1. Revised architecture
```
            ┌──────── Orchestrator: APScheduler 3.x (cron discover + DateTrigger snipe) ────────┐
 eBay Browse API ─▶ Ingest(B1) ─▶ [deterministic spec parse] ─┐
 Gmail saved-search ─▶ Ingest(B1) ─▶ Extract(B2, LLM+injection-guard) ─▶ Verify(B3) ─▶ Value(B4) ─▶ Decide ─▶ APPROVE(human) ─▶ Act(B5 Gixen)
                                                              │                                            └─ Notify(B7) digest/approval
                       └──────── SQLAlchemy2+Alembic / SQLite WAL (state, ledger, audit, <6h eBay TTL) ───────┘
            Cross-cutting from day 1: Security(B-sec) · Tests/Mocks/CI(B8) · Observability+dead-man-switch · Docs/ADRs
```

## 2. Functional blocks + chosen OSS stack
| # | Block | Stack (maintained 2026) | Key hardening |
|---|---|---|---|
| **B1** | Ingestion | `httpx` + ~30-line OAuth client-credentials helper + `tenacity` + `pyrate-limiter`(SQLite backend) for eBay; Gmail MCP for classifieds alert emails | eBay token TTL 2h (refresh ~90%); 5k/day cap tracked persistently; **<6h cache TTL** for raw eBay content (separate store from rate-limit counter); DKIM/SPF-verify alert emails, re-resolve item by id, allowlist URL hosts, block private IPs (SSRF) |
| **B2** | Extraction (classifieds free-text ONLY) | Claude **native structured outputs** (`messages.parse`, strict schema) + optional `instructor`; **`protectai/llm-guard` PromptInjection scanner** | Listing text = data, wrapped in delimiters; operator instructions only in `system`; **regex cross-validation: LLM may only narrow, never override** (Pydantic `@model_validator` intersects LLM vs regex); ignore self-reported confidence for escalation; LLM output never touches price/budget/seller-facing text |
| **B3** | Compatibility gates | **plain typed predicates** over a `Module` dataclass (+ optional `rule-engine` BSD); local SQLite **part-number→spec DB** seeded from JEDEC JESD21-C/400-5 offsets + `spdr`/`decode-dimms` parsers + Kingston/Crucial catalogs | ~20 hard gates (SODIMM≠DIMM, DDR4≠DDR5, 1.2V≠1.35V, ¬ECC, rank, pair); PN diff vs canonical; **unknown PN = "unverified", not PASS**; matched-pair gated for (2,x) |
| **B4** | Valuation | `numpy`+`scipy.stats` (MAD-trimmed median) + `pandas`/`river` (trend+staleness) + **`CurrencyConverter`** (offline ECB FX, timestamped) | Live rolling `market_ref` per (capacity,modules,speed,condition,region); **staleness gate → ALERT-only if old/thin**; landed cost = price+ship+FX+**VAT 21%**+customs+GSP fee+payment FX+**E[DOA loss]**; sold-comps gated → fall back to Browse active-ask distribution + request Insights |
| **B5** | Bidding + budget | **`httpx`** → Gixen `api.php` (`notags=1`); **reserved-budget ledger** (atomic SQL); `python-statemachine` lifecycle | `UPDATE budget SET committed=committed+:max WHERE committed+:max<=cap` (race-free); **idempotency `UNIQUE(account,ebay_item_id)`** + write-ahead PENDING intent row before Gixen call; FSM PENDING→REGISTERED→VERIFIED→FIRED→WON/LOST; re-verify snipe at T-30m; **risk-coupled, jittered** max bid; **human approval gate before register** |
| **B6** | Orchestration/persistence | **APScheduler 3.x** (AsyncIO + SQLAlchemyJobStore) + **SQLAlchemy 2.x + Alembic** + **pydantic-settings**+`keyring` + `tenacity`/`purgatory` | Event-driven: cron discovery (15–30m) + `DateTrigger(close_T−lead)` per soon-ending auction; SQLite **WAL+busy_timeout+single-writer**; jobs persist→crash-resume; startup reconciliation vs Gixen `list-snipes`; tz-aware UTC everywhere |
| **B7→B8** | Tests/CI/Obs/Docs (DAY 1) | `pytest`+`pytest-asyncio`+`pytest-cov`+`hypothesis`+`mutmut`; `respx`+`vcrpy`/`pytest-recording`; **WireMock** + fake-bidder FastAPI for live-mock; GitHub Actions; `pre-commit`; `ruff`+`mypy`; `uv` lock; `bandit`+`pip-audit`+`gitleaks`/`trufflehog`; `structlog`(redaction)+OpenTelemetry+**healthchecks.io**; `mkdocs-material`+ADRs | autouse **network-egress blocker** in tests (no real bid ever); `BIDDING_ENV=mock` refuses non-localhost bidding host; secret redaction in logs+cassettes; dead-man's-switch alerts if run misses an auction-close window |

## 3. Consolidated safety/compliance guardrails (hard-coded, non-optional)
- **Human approval before any binding bid** (default-on, not a toggle). Digest/ALERT is the product surface; snipe only on explicit per-item confirm.
- **eBay listings: deterministic only**, raw content purged <6h, no seller PII to LLM, ≤5k calls/day.
- **No scraping** — classifieds via native email alerts only; any source without alerts is excluded.
- **EU-only auto-bid**; non-EU items → ALERT (human reviews import/VAT).
- **Reserved-budget ledger** + global cap + per-item cap + max-concurrent-open-snipes; **fail-closed** kill-switch & DRY_RUN-default-true (must be auditably armed); **jittered** sub-market max bids; secret redaction; GDPR retention TTL; personal-use only.

## 4. Revised decision logic
```
landed = price + shipping + fx_fee + import_vat(country) + customs + gsp_fee + E[DOA_loss(tested,rating,protection)]
market_ref = staleness_guarded( MAD_trimmed_median( recent_sold_comps[capacity,modules,speed,cond,region] ) )
deal = clamp((market_ref - landed)/market_ref, 0, 1)
risk = Σ wᵢ·platform_verifiable_featureᵢ   # seller rating/age/feedback, buyer-protection, return-policy ONLY; self-claims neutral
adjusted = deal · risk
max_bid = min( market_ref·0.80·risk − jitter, MAX_BID_CAP )   # risk-coupled, jittered, below true value, in AUCTION's native currency + FX buffer
RESERVE budget atomically; DECIDE BID(→human approve) / ALERT / ASK-SELLER / SKIP
reservation policy: secretary-style over the buying window (strict early, relax near deadline); BIN/Best-Offer compared as first-class alternative; never greedily spend the whole cap on the first mediocre deal
```

## 5. Roadmap (engineering baked in from v0)
- **v0 — Foundation (1–2d):** repo + `uv` + `ruff`/`mypy`/`pre-commit` + GitHub Actions skeleton + SQLAlchemy/Alembic schema + pydantic-settings/keyring + structlog + healthchecks ping + WireMock fakes + network-egress test blocker + first ADRs + mkdocs. *No business logic ships without a test + a migration + a doc.*
- **v1 — Alert-only digest (3–4d):** B1(eBay+Gmail)→B2/B3 verify→B4 value→B7 digest. Golden-set (≥50 labelled listings incl. injection/DIMM-mislabel/1.35V/ECC) gates CI. No bidding.
- **v2 — Approved snipe (2–3d):** B5 ledger+Gixen+FSM, human-approval gate, DRY_RUN shadow 2 weeks, live-mock end-to-end, reconciliation. Arm only after shadow validation.
- **v3 — Classifieds assist (2–3d):** email-alert ingestion (NL/BE/FR), ASK-SELLER auto-draft (templated, no budget leak), MemTest86-on-receipt as a cost input.
- **v4 — Generalize:** pluggable compatibility profiles (SSD/GPU); revisit GDPR if scope leaves personal use.

## 6. Iterative update & "keep-everything-in-sync" strategy (your new requirement)
**Definition of Done (enforced in CI, every change):** code + unit test + property test (for money/parse) + migration (if schema) + docs/ADR update + passing live-mock + coverage ≥ gate. A PR that changes one without the others **fails CI**.
- **Contract tests** pin the shape of each external API (eBay/Gixen/Gmail/Anthropic) via recorded `vcrpy` cassettes; a nightly "drift" job replays against real sandboxes and alerts on schema drift → forces a synced update of client + mock + test together.
- **Schema/state sync:** Alembic migration required for any model change; CI runs `upgrade→downgrade→upgrade`; a check fails if models and migrations diverge.
- **Prompt/version sync:** Claude model id + extraction prompt + output schema are versioned together; the golden-set regression must pass before a prompt/model bump merges.
- **Config sync:** pydantic-settings is the single typed source; a CI check fails if `.env.example`, the settings model, and the docs table diverge.
- **Mock/real parity:** every external call goes through one client module; its WireMock stub + respx fixture live beside it; a "parity" test asserts the mock satisfies the same contract test as the recorded real response.
- **Feature flags + incremental rollout:** new sources/logic land behind flags (default off), validated in shadow/DRY_RUN, then enabled. The dead-man's-switch + daily digest header (DRY_RUN state, baseline age, discovery counts, budget committed) keep the human aware each day.
- **Dependency sync:** `uv.lock` committed; Renovate/Dependabot PRs run the full gate; `pip-audit` blocks known-vuln deps.

## 7. Antipatterns to avoid (from red-team)
LLM-as-source-of-truth for specs/prices; trusting self-reported "tested"/screenshots as positive signal; per-item-only budget checks; idempotency keyed on local id; fixed-formula guessable max bid; static baseline; daily-cron for time-critical snipes; fail-open safety; logging request bodies/secrets; scraping behind ToS; treating zero-results as success; naive local datetimes.

## 8. Open decisions
Budget cap + thresholds + 0.80 factor (calibrate in shadow); sold-comp source (pursue Insights vs active-ask proxy); host (local Task Scheduler vs small VPS — needs reliable wake before auction close); Postgres vs SQLite if concurrency grows; whether to keep eBay at all given its API-License LLM clause (mitigated by deterministic-only path).
