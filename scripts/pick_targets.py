"""Pulls the qualified companies out of Project 1 and writes the target list.

I need one row per company to watch. The company identity comes from P1's
`qualified` view, so I'm not inventing a second company list. board_token comes
out blank - I fill it in by hand after checking each careers page.
"""
import csv
import os
import sqlite3
from pathlib import Path


def load_env(path=".env"):
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
    load_env()
    db_path = os.environ.get("LEAD_DB_PATH")
    if not db_path or not Path(db_path).exists():
        print("Set LEAD_DB_PATH in .env to Project 1's database first.")
        raise SystemExit(1)

    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(qualified)")]
    if not cols:
        print("No 'qualified' view found - is this Project 1's database?")
        raise SystemExit(1)

    has_config = "config_name" in cols
    sql = "SELECT q.company_id, c.name, c.domain FROM qualified q JOIN companies c ON c.id = q.company_id"
    if has_config:
        sql += " WHERE q.config_name = 'generic_b2b_saas'"
    sql += " ORDER BY c.name"

    rows = conn.execute(sql).fetchall()
    conn.close()

    out = Path("config/boards.csv")
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["company_id", "name", "domain", "source", "board_token"])
        for company_id, name, domain in rows:
            writer.writerow([company_id, name, domain, "greenhouse", ""])

    print(f"wrote {len(rows)} companies to {out}")
    print("Next: open each company's careers page and fill in board_token.")


if __name__ == "__main__":
    main()
