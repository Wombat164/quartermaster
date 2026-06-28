"""`python -m quartermaster` -- run the Phase-1 funnel over classifieds emails, print the digest.

Alert-only, and runs with NO live keys: deterministic-only extraction (regex) + the bootstrap
baseline, reading local files. Optional upgrades, all behind config/keys:
- extraction: `QM_ANTHROPIC_API_KEY` -> Claude (else regex-only).
- baseline:   `QM_SERPAPI_API_KEY`  -> live market comps (else the bootstrap table).
- input:      `QM_MAIL_SOURCE` = file (default) | stdin | mbox | imap | gmail. file/stdin/mbox/imap
              are stdlib (imap = an app-password, any provider); gmail needs the `[gmail]` extra.
Pass file paths as arguments to read those directly, overriding the configured source.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from . import mail
from .config import Settings
from .digest import render_digest
from .fitment import G513QR
from .fx import ecb_fx_rates
from .listings import ListingSource
from .llm import anthropic_extractor
from .logging import configure_logging, get_logger
from .pipeline import BaselineResolver, RawListing, make_baseline_resolver, null_extractor, run_pass
from .ram import bootstrap_baseline
from .serpapi import fetch_shopping_comps
from .valuation import Comp


def _read(settings: Settings, paths: list[Path]) -> list[RawListing]:
    """Produce RawListings from explicit file args, else from the configured mail source."""
    if paths:
        return mail.read_paths(paths)
    src = settings.mail_source
    if src == "stdin":
        return mail.read_stdin()
    if src == "mbox":
        return mail.read_mbox(settings.mail_path)
    if src == "imap":
        password = settings.imap_password.get_secret_value() if settings.imap_password else ""
        return mail.read_imap(
            host=settings.imap_host,
            port=settings.imap_port,
            user=settings.imap_user,
            password=password,
            folder=settings.imap_folder,
        )
    if src == "gmail":
        from .gmail import read_label

        try:
            return read_label(
                settings.gmail_label,
                token_path=settings.gmail_token_path,
                client_secret_path=settings.gmail_client_secret_path,
            )
        except ImportError as exc:  # the google libs are an optional extra
            raise SystemExit("the 'gmail' source needs: pip install quartermaster[gmail]") from exc
    return mail.read_path(settings.mail_path)  # file (default)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quartermaster", description="Phase-1 deal-hunter digest."
    )
    parser.add_argument(
        "bodies", nargs="*", type=Path, help="email files (.eml/.txt); omit to use the mail source"
    )
    args = parser.parse_args(argv)

    settings = Settings()
    configure_logging(settings)
    log = get_logger("quartermaster")

    raws = _read(settings, args.bodies)
    fx = ecb_fx_rates()
    today = dt.datetime.now(tz=dt.UTC).date()

    key = settings.anthropic_api_key
    llm = anthropic_extractor(api_key=key.get_secret_value()) if key is not None else null_extractor

    baseline_for: BaselineResolver
    serp = settings.serpapi_api_key
    if serp is not None:
        serp_key = serp.get_secret_value()

        def _fetch(query: str) -> list[Comp]:
            return fetch_shopping_comps(query, api_key=serp_key)

        baseline_for = make_baseline_resolver(fetch=_fetch, fx=fx.rates)
        baseline_mode = "serpapi+bootstrap"
    else:
        baseline_for = bootstrap_baseline
        baseline_mode = "bootstrap"

    log.info(
        "ingest pass",
        listings=len(raws),
        source=("files" if args.bodies else settings.mail_source),
        extractor=("anthropic" if key is not None else "deterministic-only"),
        baseline=baseline_mode,
    )

    items = run_pass(
        raws,
        llm=llm,
        profile=G513QR,
        fx=fx,
        baseline_for=baseline_for,
        today=today,
        source=ListingSource.CLASSIFIEDS_EMAIL,
    )
    print(render_digest(items, dry_run=settings.dry_run, fx_age_days=fx.age_days(today)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
