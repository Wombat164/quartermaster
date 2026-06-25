# Quartermaster -- UX mock (digest + approval)

The two user-facing surfaces, as low-fi mocks: the **daily digest** and the
**one-click approval**. Doubles as the eBay-application artifact ("mocks of your user
experience"). Grounded in `plan-final.md` (the non-negotiables) + a best-practices
deepdive (sources at the bottom). ASCII so it renders everywhere.

## Channel model (maps to trust boundary B2)

- **Daily digest = OUTBOUND, batched.** One digest/day (not per-listing pings) ->
  respects attention, kills alert fatigue. Delivered to a surface the agent controls
  (local web view / email-to-self), NOT mixed with the inbound classifieds alert inbox.
- **Approval = OUT-OF-BAND, signed.** The APPROVE action goes through a separate
  signed-token surface, distinct from the attacker-influenceable inbound channel
  (classifieds alert emails). A button in an inbound email is never the approve path.
- **Critical push = rare, time-critical only.** An EU-eligible, verified, high-value
  item closing soon with no decision yet -> one out-of-band push. Everything else waits
  for the digest. (Severity tiering, not constant pings.)

## Mock 1 -- Daily digest

```
=============================================================================
 QUARTERMASTER -- daily digest        2026-06-25 07:00        [ DRY_RUN: ON ]
-----------------------------------------------------------------------------
 baseline: live (age 2d)    discovered: 14  (eBay 9 / classifieds 5)
 budget: EUR 120 / 400 committed (30%)   unverified 3/14 (21%)   regret 4wk: 8%
=============================================================================

 #1  [eBay]  Crucial 32GB DDR4-3200 SODIMM x2   fit: laptop-A    close in 3h12m
     deal 41%   [#####-----]  VERIFIED  | comps: live (N=12)
     landed EUR 58.40  = bid 49 + ship 6 + VAT 12.2 + FX 0.2 + DOA 0.8 (- ...)
     market_ref EUR 99      max_bid EUR 71  (mkt*0.78 - jitter, cap 80)
     >>> [ APPROVE SNIPE ]   signed, bound to this snapshot      why-ranked [v]

 #2  [classifieds NL]  G.Skill 16GB DDR4-3600 x2   fit: desktop-B
     deal 33%   [###-------]  UNVERIFIED  | source: email body only
     landed ~EUR 70 (2 cost components unknown)   market_ref EUR 105 (live N=9)
     ALERT-ONLY -- open listing to verify specs, then bid manually  [ open ]

 #3  [eBay]  Kingston 8GB DDR3-1600   fit: legacy-C            close in 1d 4h
     deal 22%   [##--------]  BOOTSTRAP comps (N=2)  | baseline STALE
     ALERT-ONLY -- thin comps, valuation not trusted yet        why-ranked [v]
=============================================================================
 Arming real bids requires: DRY_RUN=false AND a separate signed arm token.
=============================================================================
```

Why each element (best-practice -> plan):
- **Scorecard header** (DRY_RUN, baseline age, counts, budget, unverified %, regret) =
  measurable oversight (EU AI Act Art.14 / NIST AI RMF) + the calibration signal.
- **Confidence bar + VERIFIED/UNVERIFIED/BOOTSTRAP badge** = confidence visualization:
  uncertainty made legible at a glance; the human knows when to double-check.
- **Landed-cost breakdown + market_ref + comps state/N** = local explanation
  ("why this rank") -> trust + correct mental model, not a black-box score.
- **Source tag** ([eBay] / [classifieds]) = provenance cue; also the visible side of
  boundary B1 (eBay rows are deterministic-only; never an LLM-written blurb).
- **APPROVE only on #1** (verified + EU + costs known); #2/#3 are **ALERT-ONLY, no
  button** = anti-confirmation-fatigue: only biddable, trustworthy items get a one-click
  path, so the click keeps meaning.

## Mock 2 -- Approval (out-of-band, signed)

Low spend -> single click. Friction scales with spend (anti-rubber-stamp).

```
+---------------------------------------------------------------+
|  APPROVE SNIPE   (one-time, out-of-band, expires 10 min)      |
|  Crucial 32GB DDR4-3200 SODIMM x2    [eBay]    close 3h12m     |
|---------------------------------------------------------------|
|  max_bid      EUR 71     (auction currency + FX buffer)       |
|  landed est   EUR 58.40  deal 41%   market_ref EUR 99 (live)  |
|  checks       VERIFIED (12 comps) . EU seller . no unknown    |
|               costs . budget room EUR 280                     |
|  token binds  hash(item_id, max_bid, landed, market_ref, snap)|
|               -> rejects on ANY field change / reuse / expiry |
|---------------------------------------------------------------|
|     [  Approve EUR 71  ]        [ Skip ]                       |
+---------------------------------------------------------------+

 HIGH-SPEND variant (max_bid > friction threshold): type-to-confirm
+---------------------------------------------------------------+
|  This bid is EUR 240. Type the amount to confirm:  [______]   |
|     [ Confirm 240 ]   friction scales with spend              |
+---------------------------------------------------------------+
```

Why (best-practice -> plan):
- **Context-rich before commit** (intent, amounts, checks, budget room) = the documented
  HITL principle: show full context + outcomes before approve/deny; everything logged.
- **Signed token bound to a hash** = action bound to identity/state; tamper/replay/expiry
  rejected (plan non-negotiable #1).
- **Friction scales with spend** = the canonical "financial action over threshold gets a
  stricter gate" + "challenge habitual actions" trust-calibration move; defeats reflex
  approval on big bids without nagging on small ones.
- **No approve button when stale/unverified/non-EU/unknown-cost** -> auto ALERT-ONLY
  (plan: friction scales; risky -> no button at all).

## Mock 3 -- Weekly decision scorecard (in Sunday's digest)

```
 DECISION SCORECARD -- week 2026-W26
  approvals 5  | wins 2  | approve->regret 0/5 (0%)  | est. false-skips ~1
  k auto-adjust: 0.78 -> 0.77 (comps thickened)   baseline refreshed 2d ago
  budget: EUR 90 spent / EUR 400 cap   leak-detector: OK (committed == active)
```

Why: closes the loop -- the only signal that calibrates `k`/thresholds and proves the
oversight is working (risk AND friction trending down, per the HITL success metric).

## Open UX questions

1. Delivery surface for the digest: local web page (richest, supports the signed-token
   approval inline) vs Markdown email-to-self vs a TUI? (Affects v1 scope.)
2. Friction threshold for type-to-confirm: a fixed EUR amount, or a % of remaining
   budget?
3. Critical-push channel (out-of-band): ntfy / Signal / a distinct email label? Must be
   provably separate from the classifieds inbound inbox.
4. How much landed-cost breakdown to show inline vs behind "why-ranked [v]"
   (progressive disclosure to keep the digest scannable).

## Best practices applied (sources)

- HITL approval for binding/financial actions: risk-tiered friction; confirmation
  fatigue is a real security failure; context-rich, identity-bound, audited; measure
  risk AND friction. (digitalapplied.com HITL-escalation-2026; permit.io HITL;
  strata.io HITL guide -- EU AI Act Art.14 / NIST AI RMF.)
- Alert fatigue: severity-tier + channel-route; batch low-priority into a daily digest;
  group related; feedback loop on "did it lead to action." (incident.io SRE alerting;
  courier.com notification-fatigue; logicmonitor.)
- Confidence + provenance: confidence visualization (bars/%/badges) makes uncertainty
  legible; local explanation drives trust + mental model; source/provenance cues; trust
  calibration via friction + challenging habitual actions. (agentic-design.ai CVP;
  aiuxdesign.guide; Springer explainable-DSS; PMC trust-calibration.)
```
