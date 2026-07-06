# Quant Job Tracker

Daily scanner for quant finance roles. Pulls from ATS APIs (Greenhouse, Lever, Ashby, Workday), community GitHub trackers, and OpenQuant; deduplicates across sources; stores everything in SQLite; alerts you once per day with only new high-confidence postings.

## Architecture

```
GitHub Actions (daily cron)
        │
   jobtracker.cli run
        │
  ┌─────┴──────────────────────────────┐
  │ source adapters (modular)          │
  │  greenhouse / lever / ashby        │  ← enriched_companies.csv drives which
  │  workday / github_trackers /       │    firms + endpoints get hit
  │  openquant                         │
  └─────┬──────────────────────────────┘
        │ Job records
  classify (keyword rules → optional LLM pass)
        │
  dedupe (uid hash + fuzzy title within company)
        │
  SQLite (data/tracker.db, committed back to repo)
        │
  alert (Telegram / email / Twilio SMS / Slack)
```

Design choices, briefly: GitHub Actions because it's free, cron-native, and the SQLite DB committed back to the repo gives you state + history + backups with zero hosting. SQLite over Postgres because a single-user daily batch job doesn't need a server. ATS JSON APIs over HTML scraping because they're stable, fast, explicitly public, and don't break when a careers page redesigns.

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in your alert channel creds
export PYTHONPATH=src

# 1. Validate + enrich the seed firm list (probes Greenhouse/Lever/Ashby endpoints).
#    Start with high priority to keep the first run short:
python -m jobtracker.cli validate-firms --only-priority high
#    Then the rest, in chunks if you like:
python -m jobtracker.cli validate-firms --limit 100

# 2. Dry run — fetch + classify, write nothing, send nothing:
python -m jobtracker.cli dry-run

# 3. Preview — full run, alert printed to stdout instead of sent:
python -m jobtracker.cli preview

# 4. Real daily run:
python -m jobtracker.cli run
```

Tests: `PYTHONPATH=src pytest tests`

## Deploy on GitHub Actions

1. Push this repo to GitHub (private is fine).
2. Repo → Settings → Secrets and variables → Actions: add the secrets for your alert channel (see `.env.example` for names — e.g. `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
3. Adjust the cron in `.github/workflows/daily.yml` (it's UTC).
4. Run `validate-firms` locally first and commit `data/enriched_companies.csv` — the Action consumes it, it doesn't re-probe every day.
5. Manually trigger once via the Actions tab ("Run workflow") to verify.

The workflow commits `data/tracker.db` back to the repo after each run — that's the state store. Tradeoff: your repo history grows by one small binary diff per day. Fine for years at this scale; if it ever bothers you, switch to Actions artifacts or a free Postgres (Neon/Supabase) later — `db.py` is the only file that changes.

## The firm spreadsheet

`data/firms_seed.csv` is the seed (470 firms, converted from your workbook). Append new firms in the same format — see `data/firms_template.csv`. Then re-run `validate-firms`; already-verified firms are skipped unless `--force`.

`data/enriched_companies.csv` is generated, but human-editable: if the probe can't find a board, fill in `greenhouse_slug` / `lever_slug` / `ashby_slug` / `workday_cxs_url` / `official_careers_url` by hand and set `source_confidence` to `manual`. Rows with `is_relevant=needs_review` are never scraped until you flip them to `yes` — nothing is deleted, ever.

Finding a Workday CxS URL manually: open the firm's Workday careers site, open browser dev tools → Network tab, filter "jobs" — the POST endpoint of the form `https://<tenant>.wd5.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs` is what goes in `workday_cxs_url`.

## Adding a new source

1. Create `src/jobtracker/sources/mysource.py` with a class extending `SourceAdapter` and a `fetch(session, cfg, firms) -> list[Job]` method. Use `make_job(...)` to construct records — it handles uid, category, seniority, remote detection.
2. Register it in `sources/registry.py` and add a toggle under `sources:` in `config/config.yaml`.
3. Add a fixture + test in `tests/`.

Use `session.get(...)` / `session.get_json(...)` — never raw `requests` — so rate limits, retries, robots.txt, and the identifying User-Agent apply automatically.

## Scraping conduct

- robots.txt respected (toggle in config, on by default)
- 2s per-domain delay, exponential backoff on 429/5xx, 3 retries then give up
- identifying User-Agent
- structured/public JSON endpoints preferred; no login, CAPTCHA, or paywall circumvention anywhere
- a source failing ≥3 consecutive runs triggers a warning appended to your daily alert

## Config knobs you'll actually touch

`config/config.yaml`:
- `alerts.channel`: telegram | email | sms | slack | none
- `alerts.include_medium_confidence`: false by default
- `alerts.zero_update`: `short` sends a one-liner on empty days; `none` sends nothing
- `filters.seniority` / `filters.locations` / `filters.include_remote`
- `classifier.*_terms`: keyword lists for high/medium/exclude
- `classifier.llm_second_pass`: optional Anthropic re-check of medium-confidence jobs
- `allowlist_companies` / `blocklist_companies`

## Command reference

| Command | Effect |
|---|---|
| `run` | fetch → classify → dedupe → store → alert → export CSV → backup DB |
| `dry-run` | fetch + classify only; prints sample; writes/sends nothing |
| `preview` | full run but alert printed, not sent |
| `validate-firms` | enrich seed CSV by probing ATS endpoints (`--only-priority`, `--limit`, `--force`, `--no-probe`) |
| `export` | dump jobs table to `exports/jobs_export.csv` |
