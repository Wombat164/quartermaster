# Deal-Hunter + Auto-Bid Agent — Detailed Implementation Plan (v1, pre-hardening)
**Date:** 2026-06-24 · Status: DRAFT to be red-teamed. Builds on `deal-hunter-agent-design.md`.

## 0. Scope & success criteria
- **MVP goal:** every morning, a ranked email of the best-value, *compatibility-verified* RAM listings (new + used) across eBay + EU classifieds, with a suggested max bid. Later: auto-snipe eBay within budget.
- **Done =** (a) zero incompatible listings surface (no DDR5/DIMM/ECC/1.35V false-positives), (b) all-in cost (incl. shipping) ranking, (c) ≤1 false "great deal" per week, (d) a placed snipe never exceeds the budget cap.
- **Non-goals:** auto-paying on classifieds; flipping/arbitrage; non-hardware categories (until v4).

## 1. Architecture
```
                ┌─────────── Orchestrator (scheduler + state machine) ───────────┐
 SOURCES ─▶ Watcher ─▶ Normalizer ─▶ Extractor(LLM) ─▶ Verifier(fit) ─▶ Scorer ─▶ Decider ─▶ Actor
   eBay Browse API        dedup         Claude          rules+LLM        value fn    budget    Gixen / Gmail
   Gmail saved-search                                                                          (snipe / digest / draft)
   OSS classifieds mon.                         └────────── SQLite (listings, audit, state) ──────────┘
```
Single-process Python service; SQLite; cron/Task-Scheduler trigger; Gmail MCP for in/out alerts.

## 2. Tech stack & reused components
- **Lang/runtime:** Python 3.13 (`uv`), `httpx`, `pydantic`, `apscheduler`, `sqlite3`/`sqlmodel`, `tenacity` (retries), `structlog`.
- **Brain:** Anthropic API (Claude) — Extract + Verify-assist + Score-explain.
- **Bidding (reuse):** Gixen Mirror API (`api.php`).
- **eBay discovery (reuse):** Browse API (`buy/browse/v1`), OAuth client-credentials.
- **Classifieds sourcing (reuse/fork):** native saved-search email alerts → Gmail MCP; fork `BoPeng/ai-marketplace-monitor`, `GoddeerisEdouard/MarketplaceNotifier` (BE), `etienne-hd/lbc-finder` (FR).
- **Alerts:** existing Gmail MCP (digest out; alert emails in).

## 3. Data model (SQLite)
- `listings(id, source, ext_id, url, title, raw_text, type, captured_at, ends_at, price_eur, shipping_eur, seller_id, seller_rating, buyer_protection, raw_json)`
- `parsed(listing_id FK, capacity_gb, modules, module_gb, form_factor, speed_mts, voltage, xmp, ecc, rank, part_no, condition, confidence)`
- `decisions(listing_id FK, fit_status, deal_score, eur_per_gb, suggested_max_bid, action, reason, decided_at)`
- `snipes(listing_id FK, gixen_id, max_bid, status, placed_at, result)`
- `audit(ts, actor, action, payload, outcome)` · `seen_hashes(hash, first_seen)` (dedup)
- `config(key, value)` · `sellers(id, platform, rating, flags)`

## 4. Component specs
**Watcher** — pollers per source; eBay Browse `search` (filtered: category=RAM, conditions, EU sites); Gmail poll for saved-search alert emails (parse links); OSS monitor feeds. Emits raw listings; dedups via content hash.
**Extractor** — Claude structured output → `parsed` schema from title+description (+image where available). Confidence score; low-confidence → ASK-SELLER queue.
**Verifier** — deterministic gates first (cheap), LLM only for ambiguous free-text. Compatibility profile loaded from config (machine spec).
**Scorer** — value function (§6); pulls `market_ref` baselines from config; computes deal_score, €/GB, suggested_max_bid.
**Decider** — thresholds + global/per-item budget; outputs BID / ALERT / SKIP / ASK-SELLER.
**Actor** — BID→Gixen add-snipe (idempotent on listing_id); ALERT→queue for digest; ASK-SELLER→draft message; ALL→audit row.
**Notifier** — daily digest email (top N, ranked, with links + max bids + fit notes) via Gmail; immediate ping for a rare top-tier deal.
**Orchestrator** — apscheduler; per-source cadence; backoff; circuit-breaker per source; dry-run flag; kill-switch file.

## 5. Compliance guardrails (hard-coded)
- eBay: only **discovery** via Browse API; bidding only via **Gixen snipe with a pre-computed max** (sniping allowed; autonomous LLM checkout banned 2026-02-20). No HTML bid bots.
- Classifieds: no scraping beyond what saved-search emails / sanctioned OSS provide; **no auto-purchase** (no auction/no buyer API) — auto-draft inquiry only, human completes.
- Global **BUDGET_CAP** + per-item **MAX_BID_CAP**; **DRY_RUN** default true until validated; **kill-switch**; full **audit log**; rate-limit + polite backoff per source; secrets in env/credential store.

## 6. Core algorithms
**Compatibility gates (from machine profile):**
```
PASS ⇔ form_factor==SODIMM ∧ speed_mts≥3200 ∧ voltage==1.2 ∧ ¬xmp ∧ ¬ecc ∧ (modules,module_gb)∈{(2,16),(2,32)}
REJECT: DIMM, DDR4L/LPDDR4, 1.35V/XMP-only, ECC/RDIMM, speed<3200, single-stick-when-need-pair
ASK-SELLER: any required field unknown/low-confidence
```
**Value function:**
```
all_in = price + shipping + customs(non-EU)
market_ref = baseline[capacity]            # configurable; seed used-median €100/32GB, €230/64GB
deal = (market_ref - all_in)/market_ref
risk = Σ wᵢ·featureᵢ (seller_rating, tested, photo_of_label, matched_pair, buyer_protection) ∈[0.5,1]
adjusted = deal·risk
suggested_max_bid = min(market_ref·0.80, MAX_BID_CAP)
DECIDE: BID if auction ∧ PASS ∧ adjusted≥BID_TH ∧ within budget; ALERT if PASS ∧ adjusted≥ALERT_TH; else SKIP
```
**Dedup:** hash(source+ext_id) + fuzzy(title+price+seller) to catch cross-post repeats.
**Snipe registration:** idempotent; Gixen add-snipe(itemid,maxbid); store gixen_id; verify via list-snipes.

## 7. Roadmap / milestones
- **v0 — Setup (½–1 day):** repo, config, SQLite schema, eBay dev keyset + OAuth, Gixen Mirror acct, secrets, dry-run harness.
- **v1 — Alert-only digest (2–3 days):** Watcher(eBay+Gmail) → Extractor → Verifier → Scorer → daily digest. No bidding.
- **v2 — eBay auto-snipe (1–2 days):** Decider budget logic + Gixen Actor + audit + kill-switch; per-item approval toggle; flip DRY_RUN off after validation.
- **v3 — Classifieds assist (2–3 days):** fork OSS monitors (NL/BE/FR), normalize, ASK-SELLER auto-draft, MemTest86 reminder on receipt.
- **v4 — Generalize (open):** pluggable compatibility profiles (SSD/GPU/any fitment-gated part).

## 8. Testing & validation
- Golden-set of 50 hand-labeled listings (incl. tricky: DIMM mislabeled "laptop", 1.35V XMP, ECC, mixed-rank) → measure fit precision/recall.
- Shadow mode: run v2 in DRY_RUN for 2 weeks, compare suggested snipes vs actual auction outcomes before enabling.
- Budget-cap unit tests; idempotency tests for snipe registration; dedup tests.

## 9. Observability & ops
- structlog JSON logs; daily run summary; per-source success/error counters; alert on source circuit-breaker open.
- Deploy: local Task Scheduler (cron) on the ROG, or a small always-on VPS. (Snipe timing handled by Gixen, so cron cadence is fine.)

## 10. Cost model
- eBay Browse API: free (≤5k calls/day). Gixen Mirror: ~$12/yr. Anthropic API: ~$X/mo (extraction tokens; cache spec). Optional CollectAlert €2.99/mo. Hosting: ~€0 (local) or ~€5/mo VPS.

## 11. Key risks (to be expanded by red-team)
Listing-text ambiguity, stale/mispriced baselines, seller fraud/fakes, account/IP bans, Gixen dependency, budget-logic bugs, notification spam, legal drift.
