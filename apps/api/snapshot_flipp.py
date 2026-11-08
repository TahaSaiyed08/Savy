"""Fetches this week's flyers near a postal code right now and saves them under apps/api/data/, the same copy the
running API keeps fresh on its own. Only needed to warm a new checkout, or to force a re-download.

Usage: uv run python apps/api/snapshot_flipp.py [POSTAL_CODE]   (also: make flipp-snapshot [POSTAL=V6T1Z4])
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.api import flyers_live  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    postal = flyers_live.normalize(sys.argv[1] if len(sys.argv) > 1 else flyers_live.DEFAULT_POSTAL)
    if postal is None:
        sys.exit("postal code should look like V6T 1Z4")
    flyers_live.refresh(postal, force=True)
    feed = flyers_live.feed(postal)
    if feed.error:
        sys.exit(f"failed: {feed.error}")
    print(f"saved {len(feed.rows)} listings from {', '.join(feed.flyers)} near {postal}")


if __name__ == "__main__":
    main()
