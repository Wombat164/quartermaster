# Deal-Hunter + Auto-Bid Agent — Design Scaffold
**Goal:** find the best *value-for-fit* used/new RAM (and later: any hardware) across EU marketplaces, rank it, and bid/buy within a budget — compatibility-aware. **Date:** 2026-06-24. Status: design only (to implement/iterate).

---

## 1. Does this already exist? (buy-vs-build)
**No off-the-shelf product does the whole thing.** Every layer exists as a *building block*; the connective tissue is the custom value.

| Layer | Off-the-shelf? | Use / Build |
|---|---|---|
| **Auction bid mechanics** (auto max-bid snipe) | ✅ Solved — **Gixen** (free, ~$12/yr Mirror, **HTTP API**, OAuth, EU); eBay native max-bid as fallback | **REUSE** — never build bidding |
| **eBay discovery** | ✅ Official **Browse API** (free, OAuth client-creds, ~5k calls/day) | **REUSE** |
| **Per-site price alerts** | ✅ Keepa (Amazon, API), Geizhals/Idealo/Tweakers "Preisalarm", Pepper (API+RSS) | **REUSE** |
| **Per-site classifieds alerts** | ✅ Native saved-search EMAIL alerts on Marktplaats / 2dehands / Kleinanzeigen / Leboncoin (free) | **REUSE** via Gmail MCP |
| **Multi-site classifieds monitor** | ✅ OSS: `BoPeng/ai-marketplace-monitor` (LLM-scored, Claude-capable), `lbc-finder`, `marktplaats-monitor`, `GoddeerisEdouard/MarketplaceNotifier` (BE!); SaaS: CollectAlert €2.99/mo, Kleinanzeigen-Agent API | **REUSE/FORK** |
| **Payment with budget caps** | ✅ Google AP2 Intent Mandate, Visa Intelligent Commerce, Stripe/PayPal agent toolkits | REUSE *if ever needed* (not needed for v1–2) |
| **Cross-lane aggregation** (new retail + used classifieds → one ranked, all-in-cost list) | ❌ **Gap** | **BUILD** |
| **Hardware-compatibility-aware filtering** ("DDR4-3200 1.2 V SO-DIMM that fits *my* laptop") | ❌ **Gap** — every tool filters on keywords+price only | **BUILD (the core value)** |
| **Decision → bid** (connect a discovered underpriced auction to an actual bid within budget) | ❌ **Gap** | **BUILD (orchestration)** |

**Verdict:** Hybrid. Reuse Gixen (bidding) + eBay Browse API + native saved-search emails + an OSS monitor for sourcing. **Build only:** (1) compatibility-aware extraction/filter, (2) cross-platform value scoring, (3) the orchestration that turns a scored deal into a snipe.

---

## 2. ⚠️ Legal / ToS constraints (these shape "full-auto")
- **eBay bans third-party autonomous LLM "buy-for-me" / checkout agents from 2026-02-20** (allowlisted partners only). **BUT sniping with a human/agent-preset max bid is explicitly allowed.** → The compliant "full-auto" path is: **agent computes a max bid *in advance* from valuation → pushes it to Gixen → Gixen snipes at close.** That's scheduled automation (allowed), *not* live LLM decide-at-close (banned). Stay on this side of the line.
- **No open public bid API** — eBay's Offer `placeProxyBid` is partner-gated "Limited Release." So programmatic bidding = via Gixen's API, not a DIY eBay bid call.
- **Classifieds have NO buyer/checkout API** and prohibit scraping; there's **no auction** (fixed price). → "Full-auto purchase" is **not compliant** there. Best you can do: auto-discover + auto-rank + (optional) auto-draft a seller inquiry; **a human completes payment/pickup.**
- **Facebook Marketplace:** no buyer API → exclude, or alert-only with human in loop.

**So "full-auto" in practice = auto-bid on eBay auctions up to a budget-capped, pre-computed max (via Gixen); everything else is auto-rank + alert/▶human.** Always: global budget cap, per-item max, dry-run mode, kill-switch, full audit log.

---

## 3. Architecture — 5-stage pipeline
```
WATCH ─▶ EXTRACT ─▶ VERIFY(fit) ─▶ SCORE(value) ─▶ DECIDE ─▶ ACT
```
| Stage | Tech (reuse) | Output |
|---|---|---|
| **Watch** | eBay Browse API (auctions+fixed) · classifieds saved-search emails (Gmail MCP) · `ai-marketplace-monitor` fork · optional CollectAlert/Kleinanzeigen-Agent | raw listings stream |
| **Extract** | **Claude (Anthropic API)** parses title/desc/photos → schema | structured listing |
| **Verify** | rules + Claude vs. machine spec (from `pc-hardware-ram` memory) | PASS / FAIL / ASK-SELLER |
| **Score** | value function (below) | deal_score, €/GB, suggested_max_bid |
| **Decide** | threshold + budget cap | BID / ALERT / SKIP |
| **Act** | Gixen API (snipe) · Gmail (digest / seller draft) | snipe placed / email sent |

### Listing schema (Extract → JSON)
```json
{ "source":"ebay.be", "url":"...", "title":"...", "type":"auction|fixed",
  "capacity_gb":64, "modules":2, "module_gb":32, "form_factor":"SODIMM",
  "speed_mts":3200, "voltage":1.2, "xmp":false, "ecc":false, "rank":"2Rx8",
  "part_no":"CT2K32G4SFD832A", "condition":"used-tested",
  "price_eur":180, "shipping_eur":7, "ships_to_be":true,
  "seller_rating":99.2, "buyer_protection":true, "photo_of_label":true,
  "ends_at":"2026-06-27T20:11:00Z" }
```

### Compatibility filter (the BUILD core) — hard gates from machine spec
```
PASS requires: form_factor==SODIMM AND speed_mts>=3200 AND voltage==1.2
               AND xmp==false AND ecc==false
               AND (modules,module_gb) in {(2,16),(2,32)}
REJECT: DIMM(desktop), DDR4L/LPDDR4, 1.35V/XMP-only, ECC/RDIMM, speed<3200
ASK-SELLER if voltage/rank/tested unknown  →  queue a templated question
```
(Machine spec source: ASUS ROG G513QR, 2× SO-DIMM, 64 GB max, 1.2 V JEDEC DDR4-3200 — see `pc-hardware-ram` memory.)

### Value function (the "best fit for value")
```
all_in = price_eur + shipping_eur + customs(if non-EU)
market_ref = baseline[capacity]      # used median: 32GB=€100, 64GB=€230 (configurable)
deal = (market_ref - all_in) / market_ref           # % under market
risk = w1*seller_norm + w2*tested + w3*photo + w4*matched + w5*buyer_protection   # 0.5–1.0
adjusted = deal * risk
suggested_max_bid = min( market_ref * TARGET_RATIO(=0.80), BUDGET_CAP )   # auctions
DECISION: BID if type==auction AND fit==PASS AND adjusted>=BID_THRESHOLD
          ALERT if fit==PASS AND adjusted>=ALERT_THRESHOLD
          else SKIP
```

---

## 4. Phased roadmap
- **v1 — Alert-only digest (build first, zero risk).** eBay Browse API + Gmail-parsed saved-search alerts → Claude extract+fit+score → daily ranked email (via Gmail MCP) with deal scores + suggested max bids. No bidding.
- **v2 — eBay auto-snipe.** Add Gixen API: for BID-decisions, place a budget-capped snipe (pre-computed max). Per-item approval toggle; hard global cap; dry-run + audit log. (Compliant: sniping allowed.)
- **v3 — Classifieds assist.** Auto-draft seller inquiry (templated, incl. the ASK-SELLER spec questions) for top classifieds hits; human sends/pays. Optional MemTest86 reminder on receipt.
- **v4 — Generalize.** Swap the fixed RAM spec for a pluggable "compatibility profile" so it works for SSDs, GPUs, any fitment-gated part.

## 5. Reusable components (fork/subscribe)
- **Bidding:** Gixen (Mirror + API) — github refs: `cyberfox/gixen`, `dgunthor/gixen4j`.
- **eBay discovery:** `timotheus/ebaysdk-python` or raw Browse API.
- **Classifieds sourcing:** fork `BoPeng/ai-marketplace-monitor` (LLM-scored, Claude-ready) + `GoddeerisEdouard/MarketplaceNotifier` (BE) + `etienne-hd/lbc-finder` (FR).
- **Brain:** Anthropic API (Claude) for Extract + Verify + Score. **Alerts in/out:** existing Gmail MCP.

## 6. Open decisions for implementation
- Budget cap value + per-item max; ALERT vs BID thresholds; TARGET_RATIO.
- Sold-comp data for `market_ref` (eBay Marketplace Insights is gated → start with our used/new baselines, refine from observed sales).
- Run host: cron/Task Scheduler vs a small always-on service (needs to fire snipes near auction close — Gixen handles the actual last-second timing, so the agent only needs to *register* snipes ahead of time → cron is fine).
- Storage: SQLite for listings/dedup/audit log.
