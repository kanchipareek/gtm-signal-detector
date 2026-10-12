"""Prints the postings for one board, so I can eyeball what the detector will see.

Usage:  python scripts/peek_board.py vercel
"""
import sys
from pathlib import Path

# Running a file inside scripts/ makes Python look for imports in scripts/,
# not the project root. This puts the root on the path so "from src..." works.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fetch import fetch_board


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else "vercel"
    postings = fetch_board(token)
    print(f"{len(postings)} postings on {token}\n")
    for p in postings[:20]:
        print(f"  {p['title'][:55]:57} | {p['department'] or '-'}")


if __name__ == "__main__":
    main()

