# Contributing

Quartermaster is a personal project, but issues and PRs are welcome (no support guarantee).

## Dev setup

Requires **Python 3.13+** and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Wombat164/quartermaster.git && cd quartermaster
uv sync --extra dev
uv run pytest                 # 212 tests
pre-commit install            # gitleaks + the lint/type/test gate on commit
```

## The gate (CI runs all of these -- keep them green)

```sh
uv run ruff format .          # format
uv run ruff check .           # lint
uv run mypy                   # strict type-check
uv run pytest                 # tests, incl. the golden set (the v1 quality gate)
uv run bandit -q -r src       # security lint
uv run pip-audit              # dependency CVEs
```

## House rules

- The authoritative design is `docs/plan-final.md`; record any plan-affecting choice in
  `DECISIONS.md` (newest-first) so code and plan never drift.
- Money is integer **EUR cents**, never float. Money/parse code carries property tests (hypothesis).
- Untrusted email/listing text is **data, never instructions**; deterministic-only sources
  (SerpApi, eBay) must never reach an LLM (`assert_llm_allowed`).
- New extraction/fitment behaviour should add a labeled case to the golden set
  (`tests/test_golden.py`), which gates CI.
- `DRY_RUN` stays default-true; never wire autonomous spending without the human-approval gate.
