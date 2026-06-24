# Deal-Hunter Agent — FINAL Plan (v3, post two red-teams + OSS research + lean pass)
**Date:** 2026-06-24 · Supersedes v1/v2. Authoritative.

---

## 0. TL;DR + the ONE go/no-go gate
A personal agent that **filters + values + ranks** RAM listings (eBay + EU classifieds) into a daily digest, and lets you **one-click approve** a Gixen snipe. The value is the *funnel before the click* (compatibility gating + live landed-cost valuation + budget discipline), not the bid execution (Gixen already automates that).

> ### 🚦 GATE 0 (do this BEFORE writing code): confirm eBay production Browse API access.
> Red-team #2's biggest find: the **Browse API is a gated "restricted" Buy API** — production access needs a business-case review and possibly a signed contract, with "no guarantee of approval," and a personal sniping app is exactly the profile that may be **denied**. The entire eBay ROI hinges on this. **File an eBay Developer Support ticket** describing the exact use (personal, human-approved, no AI on eBay content, <6h purge) and get a written yes/no. **If denied → the eBay leg is dead; fall back to classifieds-only (thin) or manual Gixen+alerts.** This is a go/no-go, not an "open decision."

## 1. What changed through the gauntlet (v1 → final)
| Was | Now (why) |
|---|---|
| Full-auto eBay bidding | **Human one-click approval mandatory** (eBay UA bans autonomous order flows; account-ban risk). Gixen still fires unattended at close → "auto" preserved where it matters. |
| eBay text → LLM | **eBay deterministic-only**, immutable `source=ebay_api` tag + hard assert blocks LLM (API License). |
| Classifieds via scrapers, "re-resolve item" | **Contradiction removed:** no scraping, **the alert email IS the dataset** — LLM reads the email body only; missing detail → human opens the link. |
| Static `market_ref` | **Live trimmed-median + cold-start bootstrap table + bootstrap/live/stale states.** |
| Per-item budget check | **Reserved-commitment ledger WITH a mandatory release path** (the v2 ledger leaked budget forever — CRIT fix). |
| Heavy "day-1" stack | **Tiered by blast radius** — full rigor only where money/safety lives; cut SPD DB, WireMock, OTel, mutmut, ADR site, river/instructor/purgatory for v1. |

## 2. Compliance & safety core (NON-NEGOTIABLE, hard-coded)
- **Human approval before every binding bid** — via a **signed one-time token bound to `hash(item_id, max_bid, landed, market_ref, snapshot)`**; reject on any field change, reuse, or expiry; approval channel **out-of-band and distinct from the inbound alert channel** (inbound alerts are attacker-influenced). Anti-fatigue: friction scales with spend; auto-ALERT-only (no approve button) when stale/risky/unverified.
- **eBay = deterministic only**, raw content purged **<6h**, immutable `source` tag + B2 hard-assert refuses any `source=ebay_api` record, no seller PII to LLM, ≤5k calls/day.
- **No scraping. Classifieds = native saved-search alert emails only** (DKIM/SPF verify the *sender*; treat the *body* as untrusted data). Email is terminal — no automated re-resolve/fetch. **Exclude images from any LLM path.**
- **EU-only auto-bid**; non-EU → ALERT (human reviews import/VAT).
- **Fail-closed** kill-switch + **DRY_RUN default true**; arming real money requires **two independent signals** (DRY_RUN=false AND a separately-stored signed arm token); Gixen host pinned to a **compiled constant**, not config.
- GDPR retention TTL; personal-use only; secret redaction default-deny.

## 3. Money-correctness core
- **Reserved-budget ledger WITH release (the CRIT fix):** atomic `UPDATE budget SET committed=committed+:max WHERE committed+:max<=cap` to reserve; **every transition OUT of an active state (LOST/CANCELLED/ERROR/REJECTED/EXPIRED) runs `committed=committed-:max` in the SAME transaction**; a periodic **reconciler recomputes `committed = Σ(max_bid) over active rows`** and corrects drift; alert when `committed/cap` is high (leak detector).
- **Won-but-unrecorded safety:** any FIRED row past close with no outcome → **`NEEDS_HUMAN_RECONCILE` quarantine, page the human, do NOT release budget** (fail-closed on money). Reconcile via Gixen `list-snipes` + DKIM-verified eBay order-confirmation email.
- **Cold-start valuation:** ship a one-time **bootstrap €/GB table** (manual scrape of recent completed listings); every valuation tagged `bootstrap | live | stale`; require N≥k live comps before a deal may leave ALERT-only.
- **Landed cost (full):** `price + shipping + FX(timestamped ECB) + VAT(21% BE) + customs + GSP fee + payment FX + E[DOA_loss]`. Unknown cost component → ALERT, never auto-BID.
- **Bid:** `max_bid = min(market_ref·k·risk − jitter, CAP)` in the auction's native currency + FX buffer; **k auto-lowers when comps are thin** (graduated, not binary); `deal = clamp((market_ref−landed)/market_ref, 0, 1)`.

## 4. Security core
- **Injection:** classifieds text wrapped as data; operator prompt only in `system`; **llm-guard** scan; **regex×LLM cross-validation fails CLOSED on disagreement AND on regex-no-match** (→ unverified/ALERT, never PASS); a biddable spec must be **corroborated by the part-number DB** (independent source) — listing text alone can only lower trust. All regexes ReDoS-bounded. LLM output never touches price/budget/seller-facing text.
- **Source provenance:** immutable `source` tag at ingest + unit test in the golden set proving no `ebay_api` record reaches the LLM.
- **Secrets:** `keyring`; default-deny log/cassette redaction; **never record eBay content or Gixen creds to committed cassettes**; `gitleaks` pre-record + pre-commit; documented **rotation** for eBay/Gmail/Gixen/Anthropic creds; least scope (Gmail read-one-label, Browse-only).

## 5. Reliability core
- **Register early, don't depend on local liveness at T-0:** Gixen is the executor — the local box only needs to *register* the snipe well before close and verify via `list-snipes`. This removes the "machine asleep at auction close" failure entirely.
- **FSM (final):** `PENDING→REGISTERED→VERIFIED→FIRED→WON→PAID→SHIPPED→RECEIVED→TESTED→KEPT|RETURNED`, plus `ERROR/EXPIRED/CANCELLED/NEEDS_HUMAN_RECONCILE`. **Timeout edges from every non-terminal state** via a reaper job (release budget). T-lead re-verify can **cancel or reduce** a snipe (Gixen delete), not just confirm.
- **Idempotency** `UNIQUE(account, ebay_item_id, snapshot_hash)` + write-ahead PENDING row before the Gixen call; content-fingerprint dedup for relists; startup reconciliation vs Gixen.
- **Persistence:** SQLite **WAL + busy_timeout + single-writer**; Alembic migrations (CI runs upgrade→downgrade→upgrade); **scheduled backups (litestream or `.backup`) + a tested restore+reconcile drill before arming v2.**
- tz-aware UTC everywhere; zero-discovery treated as suspect (alert); **dead-man's-switch (healthchecks.io)**.

## 6. Functional blocks — LEANED OSS stack
| Block | v1 (ship now) | Defer / add later |
|---|---|---|
| Ingest | `httpx`+OAuth helper+`tenacity`+`pyrate-limiter` (eBay); Gmail MCP (classifieds emails) | — |
| Extract | Claude **native structured outputs**; **llm-guard**; regex cross-val | `instructor` (only if multi-provider) |
| Verify | **plain typed predicates** (~20 gates); unknown→unverified | **part-number SPD DB** (defer; only if manual verify proves painful) |
| Value | `numpy`+`scipy.stats` trimmed median; `CurrencyConverter`; bootstrap table | `river` trend, `pandas` windows |
| Bid+budget | `httpx`→Gixen; SQL reserved-ledger **+ release**; `python-statemachine` | secretary-style reservation (defer) |
| Orchestrate | **APScheduler 3.x**+SQLAlchemy2+Alembic; pydantic-settings+keyring; tenacity | `purgatory` breaker (defer) |
| Tests/CI/Obs | pytest+asyncio+cov; **hypothesis on money/parse**; **respx**+**vcrpy**; egress-blocker autouse; `BIDDING_ENV=mock`+localhost stub; GitHub Actions (uv lock, ruff, mypy, bandit, pip-audit, **gitleaks**); structlog redaction; **healthchecks.io**; `DECISIONS.md`+README | WireMock+FastAPI fake-bidder, `mutmut`(money files only), OpenTelemetry, mkdocs+ADR site (all defer) |

## 7. Decision-quality observability (was missing)
**Outcome ledger:** for every ALERT/approve, log predicted `deal%` + realized outcome (won price vs later market); track **approve→regret rate**, est. false-skips; weekly **decision scorecard** in the digest. This is the only signal that calibrates `k` and thresholds — without it the agent can run green for months and buy junk. Digest header shows: DRY_RUN state, baseline age, discovery counts, budget committed, unverified rate.

## 8. Roadmap (leaned)
- **v0 — Gate + thin foundation (1–2d):** ⚖️ resolve **GATE 0 (eBay access)** first. Then uv+ruff+mypy+pre-commit, GitHub Actions skeleton, SQLAlchemy/Alembic schema, pydantic-settings+keyring, structlog, healthchecks ping, respx, egress-blocker, `DECISIONS.md`. *(No SPD DB, OTel, mkdocs, WireMock, mutmut yet.)*
- **v1 — Alert-only digest (3–4d):** ingest→deterministic gates→bootstrap+live valuation→ranked digest + decision scorecard. Golden set ≥50 (incl. injection/DIMM-mislabel/1.35V/ECC/source-leak) gates CI. No bidding.
- **v2 — Approved snipe (3–4d):** signed-approval gate → reserved-ledger **with release + reconciler** → Gixen register-early + verify → 2-week DRY_RUN shadow → backups+restore drill → arm via two-signal. 
- **v3 — Classifieds assist (2–3d):** email-body-only extraction (NL/BE/FR), ASK-SELLER auto-draft (no budget leak), MemTest86-on-receipt as a cost input.
- **v4 — Generalize / won-item polish:** pluggable compatibility profiles; full post-win automation.

## 9. Engineering practices, TIERED by blast radius (your "from-the-start" + "in-sync", right-sized)
- **Tier A — money/safety code** (ledger, bid path, money math, parsers, approval, source-tag): **full rigor** — unit + property (hypothesis) + mutation (manual, money files) tests, migration + downgrade test, contract test + cassette, `DECISIONS.md` entry, **must pass to merge**.
- **Tier B — everything else:** unit test + types; docs/property tests advisory. Don't let team-grade DoD friction stall a solo project.
- **Keep-in-sync mechanisms:** one client module per external API (its respx fixture + cassette live beside it); **nightly contract-drift job** replays cassettes vs real sandboxes → alerts on schema drift (forces synced client+mock+test update); `.env.example` **generated** from the pydantic-settings model (can't diverge); model id + prompt + output schema versioned together, gated by golden-set regression; `uv.lock` committed, `pip-audit` blocks vuln deps; feature flags default-off → shadow → enable.

## 10. Won-item runbook (was missing)
On WON: notify "action needed" + payment deadline → pay → confirm shipping → receive → **MemTest86 (3–4 passes)** → KEEP or RETURN/refund → **settle ledger** (release committed → record actual spent) → feed DOA outcome back into `E[DOA_loss]`.

## 11. Residual risk register (accept / watch)
- **GATE 0 eBay access denial** → fallback = classifieds-only (thin; reconsider build) or manual.
- Approver rubber-stamping → mitigated by signed tokens + friction + scorecard, not eliminated.
- llm-guard imperfect → backstops are source-tag + "LLM never prices" + corroboration, not the scanner alone.
- Gixen single-account flood looks abusive → rate-limit registrations; Mirror sub (free tier = 4 wins/mo).
- Counterfeit/relabeled RAM → only platform-verifiable signals raise risk; MemTest86 + buyer protection; cap per-item exposure.
- Cold-start thin comps in a spike → graduated `k`, ALERT-only until N live comps, bootstrap table.

## 12. Antipatterns (do not reintroduce)
LLM-as-source-of-truth for specs/prices; trusting self-claimed "tested"/screenshots as positive; per-item-only budget; ledger without a release path; idempotency on local id; guessable fixed-formula max bid; static baseline; daily-cron for time-critical snipes; depending on local liveness at auction close; fail-open safety; logging/recording secrets or eBay content; "re-resolve" classifieds (=scraping); treating zero-results / binary-staleness as success; naive datetimes; team-grade DoD on a solo repo.
