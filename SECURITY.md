# Security

Quartermaster is a personal, security-first project. This is its security model and how to
report issues.

## Reporting a vulnerability

Please report privately via GitHub's **"Report a vulnerability"** (Security advisories) on
this repository, not a public issue. (No contact email is published, to keep the repo free
of personal data.)

## Security model

- **No secrets in the repo.** `.gitignore` blocks `.env`, `*.key`, `*.pem`, `secrets/`, and
  all DB / state files. CI runs **gitleaks** over the full git history on every push.
- **Config is separate from the program** (`src/quartermaster/config.py`, `pydantic-settings`):
  every runtime setting comes from the environment (prefix `QM_`) or a gitignored `.env`.
  Secrets are `SecretStr` -- masked in logs and `repr`, never serialized by accident.
  `.env.example` is generated from the settings model and a test fails if it drifts.
- **Secrets live in your secret store and are injected via env at runtime.** Nothing is read
  from plaintext on disk in normal use (`.env` is for local dev only). Example with Bitwarden:

  ```sh
  export QM_SERPAPI_API_KEY="$(bw get password serpapi)"
  export QM_ANTHROPIC_API_KEY="$(bw get password anthropic)"
  export QM_IMAP_PASSWORD="$(bw get password mail-app-password)"   # only for the imap source
  ```

- **Fail-safe by default:** `QM_DRY_RUN` defaults to **true** -- the agent never takes a real
  or binding action unless explicitly disarmed. (Phase-2 bidding additionally requires a second
  independent arm signal and per-bid human approval.)
- **No autonomous spending.** Phase 1 is *search + compare only* (no buy button). Phase-2
  bidding requires human one-click approval; a reserved-budget ledger enforces a hard cap and
  releases on every terminal state.
- **Network egress is blocked in tests** (autouse `tests/conftest.py::block_network`): no test
  can reach the internet or place a real action.
- **Untrusted input stays data, never instructions.** Classifieds/email content is treated as
  data; eBay content is processed deterministically and never sent to an LLM. See
  `docs/plan-final.md` (sec.2/sec.4).
- **Email-input credentials are yours, kept out of the repo.** The default `file`/`stdin` sources
  need none. IMAP uses an app-password (`QM_IMAP_PASSWORD`, from your secret store) -- that credential
  is full-mailbox scope, so prefer a dedicated forwarding account. The optional Gmail-API backend
  caches an OAuth token at `data/gmail_token.json` (gitignored, a LIVE credential -- revoke at
  myaccount.google.com); its `gmail.readonly` is a Google "restricted" scope whose unverified-app
  refresh token expires ~weekly, which is why IMAP + an app-password is the recommended live path.

## Scope / no warranty

Personal-use software provided under the MIT License "AS IS", without warranty. You are
responsible for your own API keys, any spending, and compliance with each data source's terms
of service.
