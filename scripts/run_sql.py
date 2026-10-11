"""Run a .sql file against the shared Project 1 database.

Usage:  python scripts/run_sql.py sql/01_signals.sql

The database location comes from the LEAD_DB_PATH environment variable
(put it in a .env file next to the project). This script never creates the
database - Project 1 owns it - so if the file isn't there, it stops.
"""
import os
import sqlite3
import sys
from pathlib import Path


def load_env(path=".env"):
    """Read simple KEY=VALUE lines from .env (no extra packages needed)."""
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main():
    if len(sys.argv) != 2:
        print("usage: python scripts/run_sql.py <file.sql>")
        sys.exit(1)

    load_env()
    db_path = os.environ.get("LEAD_DB_PATH")
    if not db_path:
        print("LEAD_DB_PATH is not set. Copy .env.example to .env and point it at Project 1's database.")
        sys.exit(1)
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}. Project 1 owns it - check the path in .env.")
        sys.exit(1)

    sql_file = Path(sys.argv[1])
    if not sql_file.exists():
        print(f"SQL file not found: {sql_file}")
        sys.exit(1)

    sql = sql_file.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
        print(f"applied {sql_file} to {db_path}")
        print("tables now in the database:")
        for t in tables:
            print(f"  - {t}")
    except sqlite3.Error as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
