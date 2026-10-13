"""Clears Project 2's derived rows so they can be rebuilt from scratch.

Only touches Project 2's tables - never Project 1's data.
"""
import os
import sqlite3
from pathlib import Path


def load_env(path=".env"):
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def main():
    load_env()
    conn = sqlite3.connect(os.environ["LEAD_DB_PATH"])
    for table in ("signal_deliveries", "signals", "signal_candidates"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    print("cleared signals, candidates, deliveries")


if __name__ == "__main__":
    main()
