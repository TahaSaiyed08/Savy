"""ONE-TIME setup for the Savy Genie space. Run it yourself, once, from the repo root:

    uv run --env-file .env python databricks/setup/create_genie_space.py

It writes to your Databricks workspace. In realdeal.core it:
  1. creates the tables live_listings and price_history (if they don't exist),
  2. loads the flyers this machine has already downloaded (apps/api/data/flipp_<POSTAL>.json),
  3. creates the Genie space "Savy: this week's grocery deals" over them (or updates it if it exists),
  4. saves the space id to apps/api/data/genie_space.json, which is how the API knows Genie is ready.

Afterwards set REALDEAL_DATABRICKS_SYNC=1 in .env so every flyer refresh keeps the tables current.
"""
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Lets the script import the project's own modules (apps/, shared/) when run directly as a file.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).parent))

from genie_space import DESCRIPTION, LEGACY_TITLES, TITLE, build  # noqa: E402

from apps.api import databricks_sync, flyers_live, genie  # noqa: E402


def saved_postal_codes() -> list[str]:
    # The postal codes this machine has downloaded flyers for: the data worth loading into the new tables.
    codes = (p.stem.removeprefix("flipp_") for p in sorted(flyers_live.DATA.glob("flipp_*.json")))
    return [c for c in codes if flyers_live.normalize(c) == c]


def main() -> None:
    # The script refuses to start without credentials rather than half-creating things in the wrong place.
    missing = [k for k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID") if not os.getenv(k)]
    if missing:
        sys.exit(f"set {', '.join(missing)} (run with: uv run --env-file .env python {sys.argv[0]})")
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    print(f"workspace: {w.config.host}")
    print("1. creating tables (if missing)...")
    databricks_sync.ensure_tables()

    print("2. loading downloaded flyers...")
    for postal in saved_postal_codes():
        feed = flyers_live.feed(postal)
        if feed.rows:
            databricks_sync.push(postal, feed.rows, feed.fetched_at or datetime.now(UTC))
            print(f"   {postal}: {len(feed.rows)} listings")
    if not saved_postal_codes():
        print("   none saved yet: start the API (make dev) and open the Flyers tab first")

    print("3. creating the Genie space...")
    # Re-running is safe: look for a space with our title across all pages of results, and update it if found instead
    # of creating a duplicate.
    serialized, warehouse = build(), os.environ["DATABRICKS_WAREHOUSE_ID"]
    existing, token = None, None
    while existing is None:
        page = w.genie.list_spaces(page_token=token)
        existing = next((s for s in page.spaces or [] if s.title in (TITLE, *LEGACY_TITLES)), None)
        token = page.next_page_token
        if not token:
            break
    if existing:
        w.genie.update_space(
            existing.space_id, serialized_space=serialized, warehouse_id=warehouse, description=DESCRIPTION,
            title=TITLE)  # also renames a space still carrying the old title
        space_id = existing.space_id
        print(f"   updated {space_id}")
    else:
        space_id = w.genie.create_space(warehouse, serialized, title=TITLE, description=DESCRIPTION).space_id
        print(f"   created {space_id}")

    # Saving the id is what switches the app's Ask button on (see genie.available).
    genie.SPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    genie.SPACE_FILE.write_text(json.dumps({"space_id": space_id}))
    print(f"4. saved {genie.SPACE_FILE}")
    print(f"\nDone. Open it: {w.config.host}/genie/rooms/{space_id}")
    print("Then add REALDEAL_DATABRICKS_SYNC=1 to .env and restart the API.")


if __name__ == "__main__":
    main()
