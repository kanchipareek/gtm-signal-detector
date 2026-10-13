# GTM Signal Detector

**Watches public Greenhouse job boards and fires when a company posts a senior go-to-market leadership role.**

[![detect](https://github.com/kanchipareek/gtm-signal-detector/actions/workflows/detect.yml/badge.svg)](https://github.com/kanchipareek/gtm-signal-detector/actions/workflows/detect.yml)
![python](https://img.shields.io/badge/python-3.12-blue)
![tests](https://img.shields.io/badge/tests-44%20passing-brightgreen)

A company hiring a VP of Marketing, Head of Growth, or CRO is about to spend
money on go-to-market — which makes those postings one of the earliest public
signals that a company is scaling. This project watches a configurable list of
public job boards and turns that signal into a structured, delivered event.

On its last full pass it checked **18 boards (~2,242 live postings)** and holds
**8 signals** — every one a genuine senior GTM hire — with **447 near-misses**
deliberately held back. Re-running adds nothing: the next pass reported
`0 new signals, 8 unchanged`.

## Quick start

```bash
git clone https://github.com/kanchipareek/gtm-signal-detector.git
cd gtm-signal-detector
python -m venv .venv
source .venv/Scripts/activate     # Windows (Git Bash). macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q        # 44 passed

##Features
. One signal, done properly — a senior GTM leadership hire, not a vague "job change" feed.
. Rule in config, not code — the match rule lives in config/match_rule.json; change it without touching Python.
. Precision-first — unclear postings go to a review queue instead of being guessed at.
. Idempotent by construction — re-running the detector, or replaying a delivery, never creates a duplicate.
. Failure-aware delivery — bounded-backoff retries on transient errors, dead-lettering on permanent 4xx.
. Signed webhook — HMAC over the raw body, constant-time compare, one deterministic effect per event.
. Scheduled — runs on GitHub Actions every 6 hours, with an overlap guard.

How it works
mermaid

flowchart LR
    CRON["GitHub Actions<br/>cron (6h)"] --> RD
    GH["Greenhouse<br/>board API"] --> F["src/fetch.py<br/>fetch + retries"]
    CFG["config/<br/>match_rule.json"] --> M["src/match.py<br/>classify"]
    F --> M
    M --> RD["scripts/<br/>run_detector.py"]
    RD --> DB[("shared SQLite<br/>signals  candidates")]
    DB --> D["src/deliver.py<br/>sign + retry"]
    D -->|"signed POST"| W["scripts/<br/>webhook_server.py"]
    W --> EV[("webhook_events")]
A posting moves through four stages: fetch (Greenhouse board API, with retries), classify (the rule from config/match_rule.json), store (a hit becomes a row in signals), and deliver (a signed POST to the webhook, recorded exactly once). Every stage is independent and testable on its own.

Data model

Four tables, all keyed to Project 1's companies(id) — this project reads that identity, it does not rebuild it.

Table	Holds
signals	One row per hit. UNIQUE(source, board_token, external_id, signal_type); delivery_status; repost_of.
signal_candidates	The near-miss / review holding pen.
signal_deliveries	One row per delivery attempt (retry history).
webhook_events	The receiver's idempotency ledger.

Configuration
Set these in a .env file at the project root (see .env.example). .env is gitignored.

Variable	Default	Description
LEAD_DB_PATH	—	Path to the shared SQLite database (owned by Project 1). Required.
WEBHOOK_SECRET	—	Shared secret for HMAC signing. Required by the receiver and sender.
WEBHOOK_URL	http://127.0.0.1:8000/webhook	Where the sender posts.
WEBHOOK_PORT	8000	Port the receiver listens on.


Usage
bash

# 1. detect: fetch the boards, classify, store signals
python scripts/run_detector.py

# 2. receive: start the webhook receiver (terminal 1)
python scripts/webhook_server.py

# 3. deliver: send pending signals to it (terminal 2)
python src/deliver.py


Inspect what was stored:

bash
python scripts/show_signals.py


Testing
bash

python -m pytest tests/ -v
tests/test_match.py — 30 cases covering the rule: hits, near-misses, review, department conflicts, and text normalisation.
tests/test_webhook.py — 14 cases covering failure handling: replay → one row, tampered signature → 401, malformed body → 400, retry exhaustion, dead-letter, and detector re-run.


Design decisions
. Rule-driven, not ML. Explainable, testable, and needs no training data. Every decision traces to a line in config/match_rule.json.
. Department is a conflict check, not a source of hits. Board department metadata is a coarse bucket ("Sales and Customer Success"), so a hit must be earned by the title.
. A review bucket instead of a forced yes/no. Unclear postings are held for a human, never guessed.
. 90-day re-post window. A job closed and re-listed under a new id is recorded but not re-alerted; a role that reopens after months fires again.

Known limitations
. Lever is not built. Only Greenhouse is supported. Of 59 candidate accounts, 18 have a public Greenhouse board — a real coverage limit, not a bug.
. Re-posts match exactly. A re-listed job is caught only when company + title match within 90 days; a retitled re-post looks new.
. Logs are plain text, not structured JSON.
. No CRM hand-off — the receiver records events; routing to a CRM is a later project.



Project structure


config/    match_rule.json (the rule), boards.csv (target boards)
src/       fetch.py  match.py  deliver.py
scripts/   run_detector.py  webhook_server.py  run_sql.py  build_ci_db.py
sql/       schema migrations (signals, candidates, deliveries, webhook events)
tests/     test_match.py  test_webhook.py
docs/      signal_rules.md (first-seen / unchanged / re-posted)
.github/   workflows/detect.yml (scheduled run)


License
MIT — see LICENSE.




