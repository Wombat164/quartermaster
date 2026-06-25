# Decisions

Lightweight decision log. Plan-affecting or plan-extending choices go here so code and
`docs/plan-final.md` never drift. Newest first.

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
