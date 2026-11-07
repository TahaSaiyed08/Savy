"""T&T weekly flyer -> UC Volume.

Usage: uv run python databricks/fetchers/tnt.py [--from-dir DIR]
"""
from common import run

STORE = "tnt"
# Unverified starting point; most chains serve pages through a flyer CDN (check DevTools).
START_HERE = "https://www.tntsupermarket.com/"


def fetch() -> list[bytes]:
    """Return this week's flyer pages as JPEG/PNG bytes, in page order, for a Vancouver (V6T) store."""
    raise NotImplementedError(f"TODO(workstream 1): scrape {START_HERE}, or run with --from-dir")


if __name__ == "__main__":
    run(STORE, fetch)
