"""Quartermaster -- personal value-for-fit RAM acquisition agent.

Codename Quartermaster (repo ``quartermaster``). Authoritative design:
``docs/plan-final.md``; blueprint ``docs/architecture.md``; UX ``docs/ux-mock.md``.

v0 is foundation only -- NO bidding logic, NO LLM, NO eBay calls, NO SPD part-number
DB. DRY_RUN defaults true; real money requires two independent signals (see the plan).
"""

__version__ = "0.0.0"
