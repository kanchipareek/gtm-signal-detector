-- Project 2 tables added to the shared SQLite database owned by Project 1.
-- These never alter P1's tables; they extend the same file so there is one
-- source of truth. companies(id) is P1's identity - every signal joins to it.

PRAGMA foreign_keys = ON;

-- One row per detected GTM leadership-hire signal.
CREATE TABLE IF NOT EXISTS signals (
    id               INTEGER PRIMARY KEY,
    company_id       INTEGER NOT NULL REFERENCES companies(id),
    signal_type      TEXT    NOT NULL,              -- 'gtm_leadership_hire'
    source           TEXT    NOT NULL,              -- 'greenhouse'
    board_token      TEXT    NOT NULL,              -- which board the posting came from
    external_id      TEXT    NOT NULL,              -- the board's posting id
    source_url       TEXT    NOT NULL,              -- the posting URL (provenance)
    title            TEXT    NOT NULL,
    department       TEXT,
    matched_term     TEXT,                          -- which rule term fired
    seniority        TEXT,                          -- senior | director
    first_published  TEXT,                          -- board's published date
    first_seen_at    TEXT    NOT NULL,              -- when P2 first saw it
    -- delivery state: the signal is written BEFORE any delivery attempt
    delivery_status  TEXT    NOT NULL DEFAULT 'pending',  -- pending | delivered | failed
    attempts         INTEGER NOT NULL DEFAULT 0,
    last_error       TEXT,
    next_retry_at    TEXT,
    UNIQUE (source, board_token, external_id, signal_type)
);

CREATE INDEX IF NOT EXISTS idx_signals_company ON signals(company_id);
CREATE INDEX IF NOT EXISTS idx_signals_status  ON signals(delivery_status, next_retry_at);

-- Append-only log: one row per delivery attempt (mirrors P1's crawl_log).
CREATE TABLE IF NOT EXISTS signal_deliveries (
    id            INTEGER PRIMARY KEY,
    signal_id     INTEGER NOT NULL REFERENCES signals(id),
    attempt_no    INTEGER NOT NULL,
    attempted_at  TEXT    NOT NULL,
    ok            INTEGER NOT NULL,                 -- 1 success, 0 failure
    status_code   INTEGER,
    error         TEXT,
    next_retry_at TEXT
);
