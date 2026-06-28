"""`python -m quartermaster` -- run the Phase-1 funnel over classifieds bodies, print the digest.

Alert-only, and runnable with NO live keys: deterministic-only extraction (regex) + the bootstrap
baseline. With `QM_ANTHROPIC_API_KEY` set it uses Claude for extraction. SerpApi (live baseline) and
the Gmail reader are wired later; for now bodies are `.txt` files passed as arguments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from .config import Settings
from .digest import render_digest
from .fitment import G513QR
from .fx import ecb_fx_rates
from .listings import ListingSource
from .llm import anthropic_extractor
from .logging import configure_logging, get_logger
from .pipeline import RawListing, null_extractor, run_pass
from .ram import bootstrap_baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quartermaster", description="Phase-1 deal-hunter digest."
    )
    parser.add_argument("bodies", nargs="*", type=Path, help="classifieds email body .txt files")
    args = parser.parse_args(argv)

    settings = Settings()
    configure_logging(settings)
    log = get_logger("quartermaster")

    raws = [RawListing(text=p.read_text(encoding="utf-8"), title=p.stem) for p in args.bodies]
    fx = ecb_fx_rates()
    today = dt.datetime.now(tz=dt.UTC).date()

    key = settings.anthropic_api_key
    llm = anthropic_extractor(api_key=key.get_secret_value()) if key is not None else null_extractor
    log.info(
        "ingest pass",
        listings=len(raws),
        extractor="anthropic" if key is not None else "deterministic-only",
        baseline="bootstrap",
    )

    items = run_pass(
        raws,
        llm=llm,
        profile=G513QR,
        fx=fx,
        baseline_for=bootstrap_baseline,
        today=today,
        source=ListingSource.CLASSIFIEDS_EMAIL,
    )
    print(render_digest(items, dry_run=settings.dry_run, fx_age_days=fx.age_days(today)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
