"""T&T weekly flyer -> UC Volume, via Flipp's public flyer API (shared/flipp.py).

Usage: uv run python databricks/fetchers/tnt.py [--from-dir DIR]
"""
import sys

from common import FetchResult, run

from shared import flipp

STORE = "tnt"
MERCHANT = "T&T Supermarket"  # exact Flipp merchant name


def fetch() -> FetchResult:
    r = flipp.fetch_grocery_flyer(MERCHANT, STORE)
    print(f"{STORE}: {len(r['rows'])}/{r['item_count']} items had a price, "
          f"{r['sized_count']} of those had a parseable size", file=sys.stderr)
    return FetchResult(pages=r["pages"], week=r["week"], items=r["rows"])


if __name__ == "__main__":
    run(STORE, fetch)
