# Kickoff prompt for the implementing agent

Copy-paste the block below into a fresh Claude Code session to begin implementation.

---

```
Retrieve and start implementing my "quartermaster" project.

1. Clone the repo and open it:
   gh repo clone Wombat164/quartermaster
   cd quartermaster

2. Read docs/plan-final.md IN FULL — it is the authoritative plan (it supersedes
   everything in docs/history/). Skim README.md and docs/background/ for context.
   Do not act on the history/ drafts except as background; the FINAL plan already
   absorbed two red-team passes and a lean pass.

3. Before writing any code, confirm you understand and will enforce the NON-NEGOTIABLES:
   - Human one-click approval before EVERY binding bid (no autonomous eBay bidding).
   - eBay content is deterministic-only, never sent to an LLM, purged < 6h, source-tagged.
   - No scraping; classifieds = the native saved-search alert EMAIL body is the dataset.
   - EU-only auto-bid; fail-closed kill-switch; DRY_RUN default-true; two-signal arming.
   - Reserved-budget ledger WITH a release path (released on every terminal state).

4. GATE 0 (go/no-go): the eBay leg depends on getting PRODUCTION Browse API access,
   which may be denied for a personal sniping app. Treat this as a blocker for the eBay
   leg. Ask me whether I've obtained eBay's written confirmation yet. If not, either
   (a) draft the eBay Developer Support ticket for me, or (b) start with the parts that
   don't depend on it (the v0 foundation + the classifieds-email leg), and stub eBay
   behind a feature flag.

5. Then propose — DON'T start coding yet — a concrete v0 task breakdown and any open
   questions, following the roadmap (§8) and the engineering practices TIERED BY BLAST
   RADIUS (§9): full tests/CI/mocks from day 1 on money/safety code (ledger, bid path,
   money math, parsers, approval, source-tag); lighter rigor elsewhere. Use the OSS
   stack already chosen in §6 unless you have a strong reason — record any deviation in
   DECISIONS.md.

6. After I approve the v0 breakdown, implement v0 (thin foundation): uv project, ruff +
   mypy + pre-commit, a GitHub Actions skeleton (uv lock, ruff, mypy, pytest, bandit,
   pip-audit, gitleaks), the SQLAlchemy 2 + Alembic schema (incl. the reserved-budget
   ledger with release, the snipe FSM states, and the immutable source tag), pydantic-
   settings + keyring, structlog with default-deny redaction, a healthchecks.io ping,
   respx + an autouse network-egress blocker so no test can ever place a real bid, and
   DECISIONS.md. NO bidding logic and NO SPD part-number DB in v0.

7. Keep everything in sync per §9: for money/safety changes, a PR must carry code + test
   (+ property test for money/parse) + migration (if schema) + a DECISIONS.md note, and
   pass CI. Generate .env.example from the pydantic-settings model so it can't drift.

Work in small, reviewable increments. Pause for my approval at each version boundary
(v0 → v1 → v2). Never flip DRY_RUN off or arm real bidding without my explicit go-ahead.
```

---

### Notes for whoever runs this
- The repo is now **public** under the GitHub account **`Wombat164`**. If you cloned under a different account, adjust the `gh repo clone` path.
- `docs/plan-final.md` is the single source of truth. If you change the plan, update that file and add a `DECISIONS.md` entry — don't let code and plan drift.
- The first *real* milestone after v0 is **v1 (alert-only digest, no bidding)** — get value flowing before touching money.
