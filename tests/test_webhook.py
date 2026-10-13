"""Tests for the webhook receiver and sender.

These prove the failure handling, not just the happy path: a replay records once,
bad signatures are rejected, malformed bodies are refused, a sender retry never
causes a duplicate effect downstream, and a detector re-run adds nothing.

Run with:  python -m pytest tests/ -v
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.webhook_server import sign, process_request
import src.deliver as deliver

SECRET = "test-secret"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE companies(id INTEGER PRIMARY KEY, name TEXT, domain TEXT);
        INSERT INTO companies VALUES (1,'Stripe','stripe.com');
    """)
    for name in ("01_signals.sql", "02_signal_candidates.sql", "03_webhook_events.sql"):
        c.executescript((ROOT / "sql" / name).read_text())
    yield c
    c.close()


def make_payload(**overrides):
    payload = {
        "event": "gtm_leadership_hire",
        "company_id": 1,
        "source": "greenhouse",
        "board_token": "stripe",
        "external_id": "8156998",
        "title": "Head of Sales, Billing",
        "detected_at": "2026-10-12T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def signed_headers(body):
    return {"X-Signature": sign(SECRET, body)}


def add_signal(conn, external_id="8156998"):
    conn.execute(
        """INSERT INTO signals
           (company_id, signal_type, source, board_token, external_id, source_url,
            title, department, first_published, first_seen_at, delivery_status)
           VALUES (1,'gtm_leadership_hire','greenhouse','stripe',?,'http://x/1',
                   'Head of Sales, Billing', NULL, '2026-01-01', '2026-10-12', 'pending')""",
        (external_id,),
    )
    conn.commit()


def wire_sender_to_receiver(monkeypatch, conn):
    """Make deliver.post feed the real receiver, so the loop is tested end to end."""
    def fake_post(url, secret, body, idempotency_key):
        req = deliver.build_request(url, secret, body, idempotency_key)
        status, _ = process_request(secret, dict(req.headers), req.data, conn)
        return status, None
    monkeypatch.setattr(deliver, "post", fake_post)


# --- receiver ----------------------------------------------------------------

def test_valid_event_is_accepted(conn):
    body = json.dumps(make_payload()).encode()
    status, resp = process_request(SECRET, signed_headers(body), body, conn)
    assert status == 200
    assert resp["status"] == "accepted"


def test_replay_records_exactly_one_row(conn):
    body = json.dumps(make_payload()).encode()
    headers = signed_headers(body)
    process_request(SECRET, headers, body, conn)
    status, resp = process_request(SECRET, headers, body, conn)
    assert status == 200
    assert resp["status"] == "duplicate"
    assert conn.execute("SELECT count(*) FROM webhook_events").fetchone()[0] == 1


def test_tampered_signature_is_rejected(conn):
    body = json.dumps(make_payload()).encode()
    status, _ = process_request(SECRET, {"X-Signature": "deadbeef"}, body, conn)
    assert status == 401
    assert conn.execute("SELECT count(*) FROM webhook_events").fetchone()[0] == 0


def test_missing_signature_is_rejected(conn):
    body = json.dumps(make_payload()).encode()
    status, _ = process_request(SECRET, {}, body, conn)
    assert status == 401


def test_malformed_body_is_rejected(conn):
    body = b"{not json"
    status, _ = process_request(SECRET, signed_headers(body), body, conn)
    assert status == 400


def test_missing_fields_are_rejected(conn):
    body = json.dumps({"event": "gtm_leadership_hire"}).encode()
    status, resp = process_request(SECRET, signed_headers(body), body, conn)
    assert status == 400
    assert "fields" in resp


# --- sender ------------------------------------------------------------------

def test_sender_delivers_a_pending_signal(conn, monkeypatch):
    wire_sender_to_receiver(monkeypatch, conn)
    add_signal(conn)
    delivered, failed = deliver.deliver_pending(conn, "http://x/webhook", SECRET, backoff=0.01)
    assert (delivered, failed) == (1, 0)
    assert conn.execute("SELECT delivery_status FROM signals").fetchone()[0] == "delivered"


def test_sender_replay_causes_no_duplicate_effect(conn, monkeypatch):
    wire_sender_to_receiver(monkeypatch, conn)
    add_signal(conn)
    deliver.deliver_pending(conn, "http://x/webhook", SECRET, backoff=0.01)
    # pretend it got queued again (e.g. a timeout the sender didn't see)
    conn.execute("UPDATE signals SET delivery_status='pending'")
    conn.commit()
    deliver.deliver_pending(conn, "http://x/webhook", SECRET, backoff=0.01)
    assert conn.execute("SELECT count(*) FROM webhook_events").fetchone()[0] == 1


def test_sender_marks_failed_after_retry_exhaustion(conn, monkeypatch):
    monkeypatch.setattr(deliver, "post", lambda url, secret, body, key: (None, "TimeoutError"))
    add_signal(conn)
    delivered, failed = deliver.deliver_pending(
        conn, "http://x/webhook", SECRET, max_attempts=3, backoff=0.01
    )
    assert (delivered, failed) == (0, 1)
    status, attempts, last_error = conn.execute(
        "SELECT delivery_status, attempts, last_error FROM signals"
    ).fetchone()
    assert status == "failed"
    assert attempts == 3
    assert last_error == "TimeoutError"
    assert conn.execute("SELECT count(*) FROM signal_deliveries").fetchone()[0] == 3


def test_failed_signal_is_picked_up_again(conn, monkeypatch):
    monkeypatch.setattr(deliver, "post", lambda url, secret, body, key: (None, "TimeoutError"))
    add_signal(conn)
    deliver.deliver_pending(conn, "http://x/webhook", SECRET, max_attempts=1, backoff=0.01)
    wire_sender_to_receiver(monkeypatch, conn)  # receiver back up
    delivered, failed = deliver.deliver_pending(conn, "http://x/webhook", SECRET, backoff=0.01)
    assert (delivered, failed) == (1, 0)


# --- detector idempotency ----------------------------------------------------

def test_detector_rerun_adds_no_duplicate_signal(conn):
    def insert():
        conn.execute(
            """INSERT OR IGNORE INTO signals
               (company_id, signal_type, source, board_token, external_id, source_url,
                title, first_seen_at)
               VALUES (1,'gtm_leadership_hire','greenhouse','stripe','8156998',
                       'http://x/1','Head of Sales, Billing','2026-10-12')"""
        )
    insert()
    insert()
    conn.commit()
    assert conn.execute("SELECT count(*) FROM signals").fetchone()[0] == 1
