"""Saves this week's five flyers (Flipp-sourced, structured) to apps/api/data/flipp_snapshot.json, so mock
mode can demo with real current prices instead of the small canned list in mock_data.py. Run this by hand
whenever you want fresher mock data; the API itself never calls the network for this at request time.

Usage: uv run python apps/api/snapshot_flipp.py   (also: make flipp-snapshot)
"""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.flipp import MERCHANT_TO_STORE_KEY, fetch_grocery_flyer  # noqa: E402

OUT = Path(__file__).parent / "data" / "flipp_snapshot.json"


def main() -> None:
    rows: list[dict] = []
    for merchant, store_key in MERCHANT_TO_STORE_KEY.items():
        print(f"fetching {merchant}...", file=sys.stderr)
        try:
            r = fetch_grocery_flyer(merchant, store_key)
        except Exception as e:
            print(f"  skipped: {e}", file=sys.stderr)
            continue
        rows.extend(r["rows"])
        print(f"  {len(r['rows'])}/{r['item_count']} items had a price, {r['sized_count']} of those had a "
              "parseable size", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"fetched_at": datetime.now(UTC).isoformat(), "rows": rows}, indent=2))
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
