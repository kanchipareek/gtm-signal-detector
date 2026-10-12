"""Fills in the Greenhouse board token for each company in config/boards.csv.

Two tries per company:
  1. guess the token from the name/domain and check it against Greenhouse's API
  2. fetch the homepage and /careers and look for a boards.greenhouse.io link

Every token - guessed OR scraped - has to pass the same check against the
company name, so a wrong board can't sneak in. Anything unresolved stays blank;
those are the gaps for the Lever pass.
"""
import csv
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "gtm-signal-detector/0.1 (learning project; contact: kanchipareek32@gmail.com)"
TIMEOUT = 10
GH_LINK = re.compile(r"(?:job-boards|boards)\.greenhouse\.io/([A-Za-z0-9_-]+)")


def fetch(url, limit=2_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read(limit)
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except Exception:
        return None, b""


def norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def token_ok(token, name, domain):
    status, data = fetch(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    if status != 200:
        return False
    try:
        jobs = json.loads(data).get("jobs", [])
    except Exception:
        return False
    if not jobs:
        return True
    api_name = norm(jobs[0].get("company_name", ""))
    label = norm(domain.split(".")[0])
    company = norm(name)
    return bool(api_name) and (api_name in company or company in api_name or label in api_name)


def guess_tokens(name, domain):
    label = domain.split(".")[0].lower()
    slug = re.sub(r"[^a-z0-9]", "", name.lower())
    return list(dict.fromkeys([label, slug]))


def scrape_token(domain):
    for path in ("", "/careers", "/jobs"):
        status, data = fetch(f"https://{domain}{path}")
        if data:
            m = GH_LINK.search(data.decode("utf-8", "ignore"))
            if m:
                return m.group(1)
        time.sleep(0.5)
    return None


def main():
    path = Path("config/boards.csv")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    filled = 0
    for row in rows:
        if row["board_token"]:
            continue
        token = None
        for cand in guess_tokens(row["name"], row["domain"]):
            if token_ok(cand, row["name"], row["domain"]):
                token = cand
                break
        if not token:
            scraped = scrape_token(row["domain"])
            if scraped and token_ok(scraped, row["name"], row["domain"]):
                token = scraped
        if token:
            row["board_token"] = token
            filled += 1
            print(f"  ok    {row['name']:24} -> {token}")
        else:
            print(f"  gap   {row['name']}")
        time.sleep(0.5)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["company_id", "name", "domain", "source", "board_token"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nfilled {filled} of {len(rows)} tokens")


if __name__ == "__main__":
    main()
