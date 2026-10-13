"""The webhook receiver.

Verifies the sender's signature, validates the payload, and records each event
exactly once. Idempotency is enforced by the database, so a replayed delivery
produces no second effect.

Run:  python scripts/webhook_server.py
Then POST to http://127.0.0.1:8000/webhook
"""
import hashlib
import hmac
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REQUIRED_FIELDS = ("event", "company_id", "source", "board_token", "external_id", "title", "detected_at")


def load_env(path=".env"):
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def sign(secret, body):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify(secret, body, signature):
    if not signature:
        return False
    return hmac.compare_digest(sign(secret, body), signature)


def _header(headers, name):
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def idempotency_key(payload):
    return f"{payload.get('source')}:{payload.get('board_token')}:{payload.get('external_id')}:{payload.get('event')}"


def process_request(secret, headers, body, conn):
    """Return (status_code, response_dict). Pure logic, so it's easy to test."""
    if not verify(secret, body, _header(headers, "X-Signature")):
        return 401, {"error": "bad signature"}

    try:
        payload = json.loads(body)
    except Exception:
        return 400, {"error": "invalid json"}

    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        return 400, {"error": "missing fields", "fields": missing}

    key = _header(headers, "X-Idempotency-Key") or idempotency_key(payload)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT OR IGNORE INTO webhook_events (idempotency_key, event, payload, received_at) "
        "VALUES (?,?,?,?)",
        (key, payload["event"], body.decode("utf-8"), now),
    )
    conn.commit()
    if cur.rowcount:
        return 200, {"status": "accepted", "key": key}
    return 200, {"status": "duplicate", "key": key}


class Handler(BaseHTTPRequestHandler):
    secret = ""
    db_path = ""

    def _respond(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/webhook":
            self._respond(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        conn = sqlite3.connect(self.db_path)
        try:
            status, response = process_request(self.secret, dict(self.headers), body, conn)
        finally:
            conn.close()
        print(f"{datetime.now(timezone.utc).isoformat()} POST /webhook -> {status} {response}")
        self._respond(status, response)

    def do_GET(self):
        self._respond(200, {"status": "ok"})

    def log_message(self, *args):
        pass


def main():
    load_env()
    secret = os.environ.get("WEBHOOK_SECRET")
    db_path = os.environ.get("LEAD_DB_PATH")
    if not secret or not db_path:
        print("Set WEBHOOK_SECRET and LEAD_DB_PATH in .env first.")
        raise SystemExit(1)
    Handler.secret = secret
    Handler.db_path = db_path
    port = int(os.environ.get("WEBHOOK_PORT", "8000"))
    print(f"listening on http://127.0.0.1:{port}/webhook")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
