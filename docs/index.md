# Quartermaster

!!! quote ""
    **Codename: Quartermaster** · repo `quartermaster` · *Acquisitions, rationed.*

A personal agent that finds the **best value-for-fit RAM** (and later, any fitment-gated
hardware) across EU classifieds + multi-retailer price data, and ranks it by **live landed cost
vs the market** -- so you see the best deal available now. The value is the **funnel before the
click**: compatibility gating, live landed-cost valuation, and budget discipline.

Buying stays in your hands -- a one-click-approved auction snipe within a hard budget is a
**later phase**.

[Source on GitHub](https://github.com/Wombat164/quartermaster){ .md-button .md-button--primary }
[The Plan](plan-final.md){ .md-button }
[Security](security.md){ .md-button }

## Status

- **v0 foundation** shipped: uv toolchain, the money/safety schema core (reserve-release ledger +
  FSM + source-tag), CI + an autouse network-egress blocker.
- **P1.1 fitment core** shipped: deterministic RAM compatibility gating (`assess()` ->
  PASS / UNVERIFIED / REJECT) against a target-machine profile.
- **Pivoted to SEARCH + COMPARE first** (eBay API dropped at Gate 0). Phase 1 = alert + compare
  only (no buy button); bid/buy is Phase 2.

## The non-negotiables (hard-coded)

1. **Human one-click approval before every binding bid** -- no autonomous bidding.
2. **eBay content is deterministic-only, never sent to an LLM**, purged < 6 h, source-tagged.
3. **No scraping** -- classifieds = native saved-search alert **emails**; the body is the dataset.
4. **EU-only auto-bid**; fail-closed kill-switch; `DRY_RUN` defaults **true**; two-signal arming.
5. **Reserved-budget ledger with a release path** (sum of live max-bids <= cap).

## Map

| Doc | What |
|---|---|
| [The Plan](plan-final.md) | Authoritative design (post two red-teams + the pivot). |
| [Architecture](architecture.md) | Data flows + components. |
| [UX & digest](ux-mock.md) | The digest surface + the approval-channel model. |
| [Security](security.md) | Security model + how to report a vulnerability. |
| [Decisions](decisions.md) | The ADR-style decision log. |

Background reading (why this exists, the price-API landscape, the eBay Gate-0 research) is in the
**Background** section of the nav.

## Configuration

Config is separate from the program: env vars prefixed `QM_` (or a gitignored `.env`). Secrets
live in your secret store, injected via env -- e.g. `export QM_SERPAPI_API_KEY="$(bw get password
serpapi)"`. `QM_DRY_RUN` defaults **true** (fail-safe). See [Security](security.md).
