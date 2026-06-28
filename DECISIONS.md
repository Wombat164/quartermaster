# Decisions

Lightweight decision log. Plan-affecting or plan-extending choices go here so code and
`docs/plan-final.md` never drift. Newest first.

## 2026-06-28 -- P1.4b: assemble() + CLI -- runnable end-to-end

`pipeline.py` + `__main__.py` make the funnel runnable. `assemble(extracted, *, profile, fx,
baseline_for, today) -> DigestItem | None` runs one ExtractedListing through fitment + landed cost +
baseline -> surface (None when no price). `run_pass()` batches it. `null_extractor` is a
deterministic-only LLM, so the funnel runs on the regex extractor alone when no Anthropic key exists.

- **CLI** (`python -m quartermaster`, `[project.scripts]`): reads classifieds body `.txt` files, runs
  the funnel, prints the digest. Runnable with NO live keys (deterministic extraction + bootstrap
  baseline); uses Claude when `QM_ANTHROPIC_API_KEY` is set; structured logging (secret-redacted).
- Phase-1 assembly defaults: classifieds = EU; EU + EUR -> costs-complete (price is the landed cost,
  domestic pickup); else costs-incomplete -> ALERT. Injected: LLM, FxSnapshot, baseline resolver, today.
- Demo verified: 3 fixtures -> the DDR5 kit dropped (incompatible with the DDR4 G513QR), 2 ALERT rows
  ranked by deal%.
- 8 tests (assemble paths, null_extractor, run_pass, CLI smoke x2 isolated from any local `.env`).
  145 pass; ruff/mypy-strict/bandit clean.
- REMAINING Phase-1: a SerpApi live-baseline resolver (swap bootstrap for live comps), P1.3c the
  Gmail one-label reader (feeds RawListings), healthchecks ping, golden set.

## 2026-06-27 -- P1.4a: the ranked digest (the human-facing surface)

`digest.py` -- Phase-1's only output. `DigestItem` (listing identity + `EvaluatedListing` +
extraction confidence) -> `rank()` (drop DROP-surface; APPROVE-eligible first, then deal% desc) ->
`render_digest()` (ASCII; one-line header scorecard: DRY_RUN / FX age / approve+alert counts; per-row
tag, deal%, landed EUR, confidence, and the demoting reason). Pure + deterministic, ASCII-only.

- 4 tests (tier-then-deal ordering + DROP excluded; header + rows; alert reason on the row; empty /
  drop-only). 137 pass; ruff/mypy-strict/bandit clean.
- The pipeline now renders **end-to-end** (sample verified): listing -> fitment -> landed + FX ->
  baseline -> deal% -> surface -> ranked digest.
- REMAINING Phase-1 (I/O + assembly, none safety-critical): an `assemble()` tying ExtractedListing
  -> DigestItem (one digest pass), P1.3c the Gmail one-label reader, the CLI entry point, the
  healthchecks ping, and the golden set. The funnel + cross-val + surface logic are all in + tested.

## 2026-06-27 -- P1.3b adapter: Anthropic structured-output extractor (llm.py)

The real `LlmExtractor` for ingest. Two layers so the parsing is unit-tested without the SDK or a
live call:

- `build_extractor(create=...)`: PURE core -- forces a single structured-output tool call
  (`emit_listing`, JSON-schema'd to the RAM fields), parses the tool input, defensively coerces
  values (numbers-as-strings/floats -> Decimal/int, junk -> None; never raises).
- `anthropic_extractor(api_key=...)`: thin wiring -- constructs `anthropic.Anthropic` + binds
  `messages.create`. Key passed in (from `config.anthropic_api_key`), never read here.
- Model: Haiku 4.5 default (cheap/fast for field extraction; overridable). System prompt re-states
  the data-not-instructions framing; the model has NO tools beyond the emitter (no agency), and its
  output is then cross-validated by ingest.
- Adds `anthropic` (light SDK -- httpx/pydantic, no torch). 5 tests via a fake `create` (parse,
  string/float coercion, junk->None, no-tool->empty, forced-tool + wrapped-prompt). 133 pass; clean.
- P1.3 is now complete except the I/O edge: NEXT P1.3c the Gmail one-label reader (bodies ->
  `extract_listing`), then P1.4 digest.

## 2026-06-27 -- P1.3b(ii): ingest orchestration + cross-validation (the safety core)

`ingest.py` ties the P1.3 pieces together for one classifieds body: `assert_llm_allowed` (B1) ->
guard scan -> `wrap_untrusted` + INJECTED LLM (`Callable[[str], LlmExtraction]`; the real Anthropic
client is the next thin adapter) -> cross-validate vs the regex extractor -> `ExtractedListing`.

- **Cross-validation is the safety core:** per money-critical field (price, total capacity), the LLM
  is trusted only when it AGREES with the deterministic read; on conflict the DETERMINISTIC value
  wins and confidence drops to LOW. Single-source field -> MEDIUM; agreement -> HIGH. So an injected
  or hallucinated number can at worst yield a LOW-confidence spec, never a silently-trusted one.
- Capacity is reconciled on TOTAL GB (the money value); when totals agree the LLM's NxM config is
  preferred (it parses kits better than the regex's bare-capacity guess).
- The model's enum strings (ddr_gen / form / currency) are VALIDATED into our enums, never raw.
- Unsafe body (guard flagged) -> the LLM is never called; deterministic-only, LOW.
- **Money bug caught + fixed:** `parse_price("DDR4 EUR 80")` matched the `4` in DDR4 as the price ->
  added a not-preceded-by-letter lookbehind + a regression test (found by the orchestration test).
- Tier-A: 8 ingest tests (agreement HIGH; price/capacity conflict LOW + deterministic-wins; LLM-only
  MEDIUM; unsafe-skips-LLM; boundary-block; to_listing). 128 pass; ruff/mypy-strict/bandit clean.
- NEXT: the Anthropic adapter (the real `LlmExtractor`, structured-output tool-call) + P1.3c the
  Gmail one-label reader -> then P1.4 digest.

## 2026-06-27 -- P1.3b(i): injection defense, middle ground (architecture-first, llm-guard pluggable)

Operator chose a MIDDLE GROUND between a light heuristic and the full (heavy) llm-guard dep.
`guard.py` is defense-in-depth where the strength is ARCHITECTURE, not one ML classifier:

- `wrap_untrusted(body)`: frames the body in hard delimiters as DATA, not instructions.
- `HeuristicScanner` (dependency-light): flags model-targeting injection patterns ("ignore previous
  instructions", fake `<system>` tags, "you are now", reveal-prompt, ...), strips control chars, caps
  length (8000) -> `ScanResult(safe, sanitized, reasons)`.
- `PromptScanner` Protocol = the extension point: an `LlmGuardScanner` (ML) drops in behind a future
  `guard` extra via `default_scanner()`; NO torch/transformers in the base install (pluggable-backend
  pattern, per the shared-memory reference).
- The real blast-radius limiter is downstream (P1.3b-ii): a fixed structured-output schema, NO tools/
  agency, and money-critical fields cross-validated vs the deterministic extractor -> an injection at
  worst yields a wrong RamSpec, caught -> UNVERIFIED.
- 7 tests; 120 pass; ruff/mypy-strict/bandit clean; stdlib only.
- NEXT P1.3b(ii): extraction orchestration (`assert_llm_allowed` -> guard -> injected Claude
  structured-output -> cross-val -> `ExtractedListing`), LLM client injected/mocked; then the
  anthropic adapter + P1.3c Gmail one-label reader.

## 2026-06-27 -- P1.3a: deterministic extraction (heuristic-first, the cross-val oracle)

`extract.py` -- regex parse of classifieds text into a `RamSpec` + price, NO LLM. Applies the
edge-LLM doctrine (heuristic-first / LLM-enriches): this deterministic read is both a standalone
extractor for structured listings AND the oracle the LLM path (P1.3b) must corroborate on
money-critical fields (price, capacity), else the spec stays UNVERIFIED.

- `parse_spec(text) -> RamSpec`: DDR gen, speed (MHz / MT/s / DDRx-NNNN), kit (NxM GB) or bare
  capacity (assume 1x; LLM cross-checks), form factor (SO-DIMM/UDIMM), ECC, registered. Unparsed
  fields stay None -> UNVERIFIED (never guesses a critical field into a PASS).
- `parse_price(text) -> (Decimal, Currency) | None`: currency symbol/code either side of the number;
  EU + US decimal/thousands separators normalised; non-positive / unparseable -> None.
- RAM-aware patterns + generic price parsing live in `extract.py` (the ingest concern), keeping the
  engine category-clean; generalises behind a protocol with category #2.
- Tier-A: 14 tests incl. totality properties (parse_spec / parse_price never raise on arbitrary
  text; any parsed price > 0). 113 pass; ruff/mypy-strict/bandit clean. No new deps (stdlib `re`).
- NEXT P1.3b: LLM enrichment -- Claude structured output over the email body (B1-allowed via
  `assert_llm_allowed`) + llm-guard (injection defense) + THIS extractor as cross-validation; then
  P1.3c the Gmail one-label reader.

## 2026-06-27 -- Architecture: generic engine vs category plugins (RamSpec stays)

Operator question: is `RamSpec` the right name if the app does more than RAM? Verdict + refactor.

- **`RamSpec` is correct.** It models RAM-specific fields (ddr_gen / ecc / registered / voltage)
  meaningless to other categories; a generic name would lie + invite cramming. Generalisation =
  category-specific specs behind a generic funnel, NOT one renamed spec.
- The funnel is **already generic**: evaluate / Surface / Listing / LandedCost / FxRates / Comp /
  live_baseline / deal_pct / ledger / FSM / the LLM-routing boundary are category-agnostic, and
  `evaluate()` depends on a generic `Assessment`, not `RamSpec`. RAM-specificity is localized to
  `fitment.py` (compatibility).
- **Fixed two leaks:** RAM bits had crept into generic modules -- `bootstrap_baseline` +
  `BOOTSTRAP_EUR_PER_GB` (in valuation) and `query_for` (in serpapi). Moved both into a new
  `ram.py` (RAM category glue: search-query builder + cold-start pricing). `valuation.py` +
  `serpapi.py` are now category-clean; `valuation._to_cents` became public `to_cents`.
- **Generalisation shape (deferred until category #2):** add a sibling category module (e.g.
  `ssd.py`: its spec + gates + query + bootstrap) and extract a thin `Fitment` protocol so
  `assess()` takes an injected gate set. NOT built now -- you can't design that abstraction well
  from a single example.

99 tests pass; ruff/mypy-strict/bandit clean. Pure move, no behaviour change.

## 2026-06-27 -- Plumbing: structlog redaction (GAP-2) + Phase-1 Listing/LLM-routing (GAP-3)

The two deferred red-team prereqs, landed before P1.3's LLM path.

- **logging.py (GAP-2):** `configure_logging(settings)` wires structlog (JSON, level filter, ISO
  timestamp) with a **default-deny redaction processor** -- any field whose KEY matches a secret
  marker (api_key / token / password / secret / authorization / ping_url / ...) is masked, so a
  secret can't reach a sink even if a caller puts it in an event. A test proves a logged
  `serpapi_api_key` value never appears in output. Born redacted, before the first client logs.
- **listings.py (GAP-3):** `Listing` (Phase-1 discovered-item record: source/title/url/price/...,
  separate from the Phase-2 `Snipe.Source`) + `ListingSource` (CLASSIFIEDS_EMAIL / SERPAPI_SHOPPING /
  EBAY) + the **B1/B2 boundary**: `llm_allowed` / `assert_llm_allowed` -> only classifieds-email
  bodies may reach an LLM; SerpApi + eBay are deterministic-only and raise `LlmBoundaryViolation`.
  The guard + its test exist NOW so P1.3 cannot regress the source-leak boundary.
- Adds `structlog`. 99 tests pass; ruff/mypy-strict/bandit clean (tests ignore S105/S106 -- fake
  secret fixtures).

This closes the red-team's "composition + plumbing" prereq (evaluate seam + GAP-2 + GAP-3). NEXT:
P1.3 ingest (classifieds alert-email extraction via LLM + llm-guard + regex cross-val; eBay
deterministic-only) -> P1.4 ranked digest + scorecard + CLI + golden set.

## 2026-06-27 -- P1.2b (ii): SerpApi Google-Shopping client (closes P1.2)

The data source that produces the `Comp` list for `live_baseline`. `serpapi.py`:

- `fetch_shopping_comps(query, *, api_key, gl, hl, ...)` -> GET SerpApi google_shopping -> parse
  `shopping_results` -> `Comp(price, currency, source="serpapi_google_shopping")`. Price from
  `extracted_price` (Decimal via str, no float math); currency from the formatted-price symbol
  (EUR/GBP/USD) with the request locale as fallback. Skips price-less / non-positive items; raises
  `SerpApiError` on a SerpApi error payload, `httpx.HTTPStatusError` on a bad status. `query_for(spec)`
  builds the search string from a RamSpec.
- **Deterministic-only (boundary B2):** only numeric price + currency + source are kept; no listing
  text, never sent to an LLM.
- **Secret handling:** the key is a query param (SerpApi's design) so the URL holds it -- never
  logged; passed in by the caller (unwrapped from `config.serpapi_api_key`), never read from disk.
- Adds `httpx`. respx-mocked tests (7); the egress backstop guarantees no live call in CI; a live
  smoke run stays manual/local with the real Bitwarden key.
- Follow-ups (noted): tenacity retry + pyrate-limiter rate-limit (plan sec.6); query tuning; seller/
  condition filters. structlog + redaction (red-team GAP-2) still precedes any logger here.

**P1.2 is now end-to-end:** SerpApi comps -> trimmed-median market_ref -> deal% -> evaluate() surface.

## 2026-06-27 -- P1.2b (i): live trimmed-median baseline (pure money core)

The compare half of P1.2, money core first. `valuation.py` gains `Comp` (a deterministic price
comparable, NEVER sent to an LLM) + `live_baseline(comps, fx)`:

- Each comp is FX-converted to EUR cents, then a **10%-trimmed median** -> `market_ref` (robust to a
  single mispriced listing). Tagged `LIVE`, carrying `n_comps`.
- Below `MIN_LIVE_COMPS` (5) -> `None`; the caller falls back to the bootstrap table (BOOTSTRAP tag),
  so the funnel keeps thin-comp listings ALERT-only (plan sec.3 "thin comps -> ALERT").
- DEVIATION: a stdlib trimmed median instead of numpy/scipy (plan sec.6) -- dep-light + exact on
  integer cents; revisit if weighting / IQR is needed.
- Tier-A: 5 tests (too-few -> None, exact median, outlier-resistance, currency conversion, +
  property: result within the [min, max] comp range). 83 pass; ruff/mypy-strict/bandit clean.
- NEXT P1.2b (ii): the SerpApi Google-Shopping client (httpx, respx-mocked) that *produces* the
  `Comp` list from live data, reading the key from `config.serpapi_api_key`.

## 2026-06-27 -- The evaluate() seam: fit + value -> surface (red-team GAP-1)

`src/quartermaster/evaluation.py` composes the two pure cores into one `EvaluatedListing` with a
`Surface` decision -- the first place fitment + valuation are exercised together (they were disjoint
libraries; this was the red-team's #1 structural gap).

- `Surface`: DROP (hard-incompatible, not shown) / ALERT_ONLY (surfaced for a human; the Phase-1
  default, never auto-actioned) / APPROVE_ELIGIBLE ("would be approvable" -- no button in Phase-1).
- `evaluate(assessment, landed_cents, baseline, *, is_eu, costs_complete, fx_age_days)` (pure):
  REJECT -> DROP (blockers travel with it); else APPROVE_ELIGIBLE only when ALL of {verdict PASS,
  baseline LIVE, EU, costs complete, FX fresh (<= 4d)} hold; otherwise ALERT_ONLY with the demoting
  reasons attached. This is where the red-team's staleness->ALERT + incomplete-cost->ALERT now live.
- Tier-A: 9 tests (one per surface path + a property: REJECT always DROPs; APPROVE_ELIGIBLE implies
  every safety condition). 78 pass; ruff/mypy-strict/bandit clean. No new deps.
- `is_eu` / `costs_complete` + the raw listing record are INPUTS here; they get a home on the
  Phase-1 `Listing` model next (GAP-3). P1.2b's live baseline plugs straight into `baseline`.

## 2026-06-27 -- Red-team pass: foundation hardening (pre-P1.2b)

Three independent adversarial reviews (money-correctness, security/safety, gap-analysis) before
building further. The foundation was found sound (integer-cents math, ledger atomicity, release-
exactly-once, no float leakage, no secrets/PII, no network/autonomous-action path yet). Fixes this
increment:

- **fitment (HIGH bug):** a malformed spec (`capacity_gb_per_module <= 0` / `module_count <= 0` /
  negative) previously returned PASS -- surfacing garbage as biddable and feeding a negative
  `market_ref`. Both CRITICAL gates now REJECT non-positive values; property tests cover it.
- **FX hardening:** `FxRates` enforces a per-currency plausibility band (0.1..10 EUR/unit) so a
  mis-scaled/inverted rate (e.g. USD=100) fails closed instead of silently 100x-ing landed cost;
  `FxSnapshot.age_days` clamps at 0 (clock skew can't read as "fresh").
- **LandedCost validation:** rejects negative price/shipping and `import_vat_rate` outside [0,1)
  (catches the 21-vs-0.21 fat-finger).
- **FSM fail-closed (money):** removed the `FIRED -> ERROR` edge -- a fired-but-unconfirmed snipe
  routes only to NEEDS_HUMAN_RECONCILE (still holding); the sole budget-releasing edge out of FIRED
  is a confirmed LOST. Property test asserts it.
- **Egress backstop hardened:** also guards `connect_ex` + `getaddrinfo` (DNS); wording softened
  (respx is the primary control, this is the backstop). New test covers connect_ex + DNS.
- **bootstrap table:** test asserts it covers every `DdrGen`; `.github/dependabot.yml` added
  (github-actions + uv, weekly).

69 tests pass; ruff/mypy-strict/bandit clean.

**DEFERRED -- reviewers converged that a small composition+plumbing increment should precede P1.2b**
(each is cheap now, expensive after network/LLM code):
1. `evaluate()` + `EvaluatedListing` -- the missing seam composing source + RamSpec + verdict +
   landed cost + deal% + provenance; hosts the staleness->ALERT and incomplete-cost->ALERT rules.
2. structlog + secret redaction -- must precede the first secret-bearing client (SerpApi).
3. Phase-1 `Listing` model + source taxonomy (`SERPAPI_SHOPPING`) + `llm_allowed` routing + the B1
   source-leak guard test -- so comp data is deterministic-only from the first byte.
THEN P1.2b (live SerpApi trimmed-median baseline) -> P1.3 ingest -> P1.4 digest + golden set.

Smaller deferred (documented, not yet fixed): landed-cost completeness flag (customs/GSP/payment-FX/
E[DOA] are an additive under-estimate -> inflates deal% cross-border; force ALERT until modelled);
`create_snipe` reserve-before-idempotency-insert (add SAVEPOINT + regression test); `Snipe.budget_id`
scoping for `reconcile`; VCR cassette redaction (before vcrpy lands); pin Actions to commit SHAs;
mid-lifecycle FSM timeout edges; 1.35V SO-DIMM -> RISK; PROMPT-FOR-RCDE.md "rcde" codename (scrub vs
remove -- operator call).

## 2026-06-27 -- P1.2a: valuation money core (EUR/USD/GBP first-class)

The Phase-1 "value" block, pure + network-free (`src/quartermaster/valuation.py`). Money in
`Decimal`, rounded to integer **EUR cents** (the ledger unit).

- **EUR / USD / GBP are first-class** (`Currency` enum + `FxRates`): no currency is special-cased --
  EUR just has rate 1. `FxRates` validates every currency is present + positive and EUR == 1. EUR is
  the settlement/comparison base (the ledger is EUR cents); listings + comps may be priced in any
  first-class currency and convert via one FX snapshot (sourced upstream, e.g. ECB).
  **(Operator directive: make USD + GBP first-class just like EUR.)**
- `LandedCost.eur_cents(fx)`: `(price + shipping) * fx -> + import VAT -> ROUND_HALF_UP to cents`.
  `import_vat_rate` defaults 0 (private EU classifieds add none); > 0 for cross-border/retail.
- `bootstrap_baseline(spec)`: cold-start EUR/GB table -> a `Baseline` tagged `bootstrap`
  (vs `live`/`stale`) so every valuation carries provenance (plan sec.3 cold-start + sec.7).
- `deal_pct = clamp((market_ref - landed) / market_ref, 0, 1)`.
- Tier-A: 15 worked examples + 4 hypothesis properties (eur_cents non-negative + monotonic in price;
  EUR conversion is identity; deal_pct stays in [0,1]). valuation.py 98% cov; ruff/mypy-strict/bandit
  clean; 59 tests pass. No new deps (stdlib `Decimal`).
- **FX source (NOT hardcoded):** `fx.py::ecb_fx_rates()` builds a timestamped `FxRates` snapshot
  from ECB euro reference rates via the `currency_converter` library (bundled + refreshable;
  `FxSnapshot.as_of` lets callers guard staleness). The `0.92 / 1.17` literals exist only in tests.
- **Scope:** the LIVE SerpApi Google-Shopping comp baseline (real comps -> trimmed median) is P1.2b.

## 2026-06-27 -- Repo renamed: deal-hunter-agent -> quartermaster

Aligned the repo slug + Pages URL with the project/package/brand name (operator request). All
references updated; docs site now at <https://wombat164.github.io/quartermaster/>.

## 2026-06-27 -- Docs site: MkDocs Material + GitHub Pages (docs-as-code)

A docs site accompanies the repo (the plan's deferred "mkdocs + ADR site", sec.6). Chose **MkDocs
Material -> GitHub Pages** over the GitHub Wiki: docs-as-code (versioned with the repo, PR-reviewed,
CI-built `--strict`) instead of an out-of-band wiki.

- `mkdocs.yml` (Material theme, light/dark, nav over the existing `docs/` tree). Added a `docs`
  optional-dependency extra (`mkdocs-material`).
- `docs/index.md` landing page. `docs/security.md` + `docs/decisions.md` **include the canonical
  root `SECURITY.md` / `DECISIONS.md`** via `pymdownx.snippets` (`--8<--`) -- single source of truth,
  no drift.
- `.github/workflows/docs.yml`: builds `mkdocs build --strict` (fails on broken links/orphans) and
  deploys to Pages (least-privilege `pages: write` + `id-token: write`; `configure-pages enablement`).
- `site/` + `.cache/` gitignored; README links the site (https://wombat164.github.io/quartermaster/).

## 2026-06-27 -- Public-first posture: MIT license, config separation, security docs

The repo goes **public** from here (operator decision: public from the get-go). Pre-flip audit:
gitleaks full-history = no leaks; no PII / no tracked secrets or DB state; `.gitignore` already
blocks every secret/state class. Changes:

- **License: MIT** (was "Proprietary -- personal use only"). `LICENSE` added; `pyproject` updated.
  Copyright "2026 Wombat164" (the repo's pseudonymous owner; keeps it PII-free).
- **Config separation (12-factor):** `src/quartermaster/config.py` (pydantic-settings, added as a
  runtime dep -- on-plan per sec.6). Runtime config via env (prefix `QM_`) or a gitignored `.env`;
  `dry_run` defaults **True** (fail-safe). Secret fields are `SecretStr` (masked, never logged).
  `.env.example` is rendered FROM the model (`render_env_example`) with a drift test -- can't diverge.
- **Secrets in the operator's store (Bitwarden), injected via env** at runtime
  (`export QM_SERPAPI_API_KEY=$(bw get password serpapi)`); never committed/read-from-disk in normal
  use. **DEVIATION/extension** from the plan's keyring-only note (sec.4/sec.6): Bitwarden is the
  operator's actual secret store; keyring stays a supported alternative backend.
- **SECURITY.md** added: security model + private vuln reporting via GitHub security advisories.
- README: Configuration & secrets section + License/Security pointers.
- Tests: `tests/test_config.py` -- fail-safe `dry_run` default, `.env.example` no-drift, SecretStr
  never leaks in `repr`/`str`.

## 2026-06-27 -- P1.1: fitment + compatibility core (the verify funnel)

First Phase-1 (search+compare) increment. `src/quartermaster/fitment.py`: a deterministic,
network-free RAM compatibility filter -- the "funnel before the click" (plan sec.4 verify block).

- **Model:** `RamSpec` (all fields Optional; `None` = "not stated" = unknown) + `FitmentProfile`
  (target-machine constraints). A concrete `G513QR` profile seeds it -- the project's founding
  use-case (ASUS ROG Strix G15 G513QR: DDR4-3200 SO-DIMM, 2 slots, 64 GB max [2x32], non-ECC, 1.2 V).
- **Gates:** 9 pure `(spec, profile) -> GateResult` predicates (ddr_gen, form_factor, buffered,
  ecc, per_module_capacity, kit_fit, dual_channel, speed, voltage). `assess()` aggregates: REJECT
  dominates; else any RISK or any CRITICAL-gate UNKNOWN -> UNVERIFIED; else PASS. Honours the plan's
  "unknown on a critical gate -> never PASS" rule.
- **Verdict semantics:** REJECT (hard-incompatible) / UNVERIFIED (missing critical data OR a risk
  like ECC-on-non-ECC) / PASS (fits; compatible-but-suboptimal stays PASS with a note, e.g.
  single-channel or below-rated speed).
- **Choices / deviations:** unstated `registered` assumed unbuffered (SO-DIMM RDIMM is exotic);
  ECC-on-non-ECC -> RISK (UNVERIFIED), not REJECT (usually boots as non-ECC, not guaranteed);
  speed + voltage are non-critical (a same-gen module always runs, just maybe slower / at JEDEC).
- **Tier-A rigor (sec.9):** 13 worked examples (one per path) + 5 hypothesis properties (assess is
  total; unknown-critical never PASSes; wrong-gen always REJECTs; oversized-module always REJECTs;
  in-spec matched kits always PASS). fitment.py 100% cov; ruff + mypy-strict + bandit clean; suite
  37 passing. No new runtime deps (stdlib `dataclasses`+`enum`); no LLM, no network.
- **Scope:** consumes an already-structured `RamSpec`; free-text -> `RamSpec` extraction (LLM +
  llm-guard) is P1.3, and the gate set will grow (CAS latency, mislabel heuristics, the v1 golden set).

## 2026-06-26 -- STRATEGIC PIVOT: search+compare first; bid/buy deferred; eBay API dropped

**Gate 0 RESOLVED -> NO-GO on the eBay API.** The deep-research
(`docs/background/ebay-gate0-research.md`) found production eBay Buy/Browse API access is
partner-only, business-model-gated, "no guarantee", with no surfaced precedent of a
granted personal/hobbyist app -- too uncertain to build on. Our design is compliant; the
risk is commercial rejection, not legality. Decision:

- **DROP the eBay API dependency.** eBay becomes manual-only (browse + manual Gixen
  later). No EPN application blocks development.
- **PIVOT the product to SEARCH + COMPARE first:** discover available value-for-fit RAM
  and rank by landed cost vs a live market baseline -- the "funnel before the click" that
  was always the stated core value.
- **DEFER bid/buy** (Gixen snipe + approval + the ledger/FSM built in increment 2) to
  **Phase 2.** Increment 2 is NOT wasted -- it is the tested Phase-2 foundation, sitting
  ready.
- **Data sources (compliant, no eBay API, no scraping):** discovery = classifieds
  saved-search ALERT EMAILS (body = dataset); compare baseline = **SerpApi** Google
  Shopping (retail + Amazon + eBay listings AS PRICE COMPS, incl EU) + a bootstrap EUR/GB
  table. NOTE: dropping the API does NOT lose the eBay *price* signal (SerpApi surfaces
  eBay via Google Shopping); we lose only API-driven eBay *sniping* (deferred anyway).
- **Roadmap reshaped:** Phase 1 = search+compare (alert/compare-only, NO approve button);
  Phase 2 = bid/buy. plan-final.md carries a pivot banner; the detailed design there
  remains valid for Phase 2 + the engine.

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
