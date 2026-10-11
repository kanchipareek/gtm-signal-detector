-- Project 2: the holding pen for postings that are NOT hits.
-- Mirrors P1's match_candidates: every non-hit worth a human look is recorded
-- here with the reason, so the detector can report a precision story
-- ("N hits fired, M near-misses held back") instead of silently dropping them.

CREATE TABLE IF NOT EXISTS signal_candidates (
    id              INTEGER PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    source          TEXT    NOT NULL,
    board_token     TEXT    NOT NULL,
    external_id     TEXT    NOT NULL,
    source_url      TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    department      TEXT,
    label           TEXT    NOT NULL,   -- 'near_miss' | 'review'
    reason          TEXT,               -- why it did not qualify as a hit
    first_seen_at   TEXT    NOT NULL,
    UNIQUE (source, board_token, external_id)
);

CREATE INDEX IF NOT EXISTS idx_candidates_label ON signal_candidates(label);
