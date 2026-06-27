"""Application configuration -- 12-factor: config lives OUTSIDE the program.

Everything runtime-tunable comes from the environment (prefix ``QM_``) or a local,
gitignored ``.env``; secrets are ``SecretStr`` and are never logged or committed.
``dry_run`` defaults to **True** (fail-safe: the agent never acts for real unless
explicitly disarmed).

Secrets live in the operator's secret store (e.g. **Bitwarden**) and are injected via env
at runtime -- ``export QM_SERPAPI_API_KEY=$(bw get password serpapi)`` -- never read from
plaintext on disk in normal use. See SECURITY.md.

``.env.example`` is rendered FROM this model by ``render_env_example`` and a test asserts the
two never drift (the plan's "can't diverge" mechanism, sec.9).
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "QM_"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- behaviour ---
    dry_run: bool = Field(
        default=True, description="Fail-safe: never act for real unless explicitly False."
    )
    data_dir: Path = Field(
        default=Path("data"), description="Gitignored runtime state (db, backups)."
    )
    log_level: str = Field(
        default="INFO", description="structlog level (DEBUG/INFO/WARNING/ERROR)."
    )

    # --- secrets (injected from your secret store via env; never committed or logged) ---
    serpapi_api_key: SecretStr | None = Field(
        default=None, description="SerpApi key (Phase-1 Google-Shopping price baseline)."
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None, description="Anthropic API key (LLM listing extraction)."
    )
    healthchecks_ping_url: SecretStr | None = Field(
        default=None, description="healthchecks.io dead-man's-switch ping URL."
    )


def _is_secret(annotation: object) -> bool:
    return annotation is SecretStr or SecretStr in get_args(annotation)


def render_env_example() -> str:
    """Render ``.env.example`` from the Settings model so the two can never drift."""
    lines = [
        "# Quartermaster configuration. Copy to .env (gitignored) and fill in.",
        "# All variables are prefixed QM_. Secrets come from your secret store (e.g. Bitwarden),",
        "# injected via env -- NEVER commit real secrets. See SECURITY.md.",
        "",
    ]
    for name, field in Settings.model_fields.items():
        env = f"{ENV_PREFIX}{name}".upper()
        if field.description:
            lines.append(f"# {field.description}")
        if _is_secret(field.annotation):
            lines.append(f"{env}=")
        else:
            default = field.default
            value = "true" if default is True else "false" if default is False else str(default)
            lines.append(f"{env}={value}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
