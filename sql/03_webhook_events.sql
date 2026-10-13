CREATE TABLE IF NOT EXISTS webhook_events (
    id              INTEGER PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    event           TEXT NOT NULL,
    payload         TEXT NOT NULL,
    received_at     TEXT NOT NULL
);
