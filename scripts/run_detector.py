"""Runs the detector: fetch each board, classify every posting, store the result.

Hits go to `signals`; near-misses and reviews go to `signal_candidates`.
Re-running is safe - the unique keys stop duplicates, so nothing is written twice.
"""
import csv
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fetch import fetch_board, FetchError
from src.match import classify, load_rule

SIGNAL_TYPE = "gtm_leadership_hire"


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
        print("Set LEAD_DB_PATH in .env first.")
        raise SystemExit(1)

    rule = load_rule()
    boards = [r for r in csv.DictReader(Path("config/boards.csv").open(encoding="utf-8"))
              if r["board_token"].strip()]
    print(f"checking {len(boards)} boards")

    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_hits = seen_hits = new_cands = seen_cands = skipped = 0

    for row in boards:
        token = row["board_token"].strip()
        company_id = int(row["company_id"])
        try:
            postings = fetch_board(token)
        except FetchError as exc:
            print(f"  ! {row['name']}: {exc}")
            continue

        board_hits = 0
        for p in postings:
            label = classify(p["title"], p["department"], rule)
            if label == "hit":
                cur = conn.execute(
                    """INSERT OR IGNORE INTO signals
                       (company_id, signal_type, source, board_token, external_id,
                        source_url, title, department, first_published, first_seen_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (company_id, SIGNAL_TYPE, "greenhouse", token, p["external_id"],
                     p["source_url"], p["title"], p["department"],
                     p["first_published"], now))
                if cur.rowcount:
                    new_hits += 1
                    board_hits += 1
                else:
                    seen_hits += 1
            elif label in ("near_miss", "review"):
                cur = conn.execute(
                    """INSERT OR IGNORE INTO signal_candidates
                       (company_id, source, board_token, external_id, source_url,
                        title, department, label, first_seen_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (company_id, "greenhouse", token, p["external_id"],
                     p["source_url"], p["title"], p["department"], label, now))
                if cur.rowcount:
                    new_cands += 1
                else:
                    seen_cands += 1
            else:
                skipped += 1

        conn.commit()
        print(f"  ok {row['name']:22} {len(postings):3} postings, {board_hits} new hits")
        time.sleep(0.5)

    conn.close()
    print(f"\nnew signals {new_hits} (seen {seen_hits}) | "
          f"new candidates {new_cands} (seen {seen_cands}) | not_a_hit {skipped}")


if __name__ == "__main__":
    main()
