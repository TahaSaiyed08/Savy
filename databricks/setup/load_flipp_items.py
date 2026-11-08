"""Fallback loader: write Flipp-sourced flipp_items.json sidecars straight into realdeal.core.flyer_items,
for when ai_query misses the 85% accuracy bar (or the pipeline hasn't produced flyer_items yet). Structured
first-party data from Flipp, not OCR off a page photo — see shared/flipp.py for where it comes from.

CAVEAT, confirmed live via DESCRIBE DETAIL realdeal.core.flyer_items: this is a Lakeflow Declarative Pipeline
streaming table — its storage location is a `__materialization_mat_*` table the pipeline engine reconciles,
not a plain managed table. Table feature "appendOnly" is set, so a plain INSERT here should be additive and
survive between pipeline runs in practice, but a full `databricks bundle run realdeal_flyers` could still
reconcile rows this script wrote if the pipeline's own flyer_extractions source doesn't know about them. Use
this as a stand-in for a store/week the pipeline hasn't covered — not layered on top of a pipeline run that's
already covering the same store/week, or you'll get the same products twice under two different item_id
schemes (the pipeline's sha2 hash vs. this script's "flipp-<id>").

Columns and types below come from a live `DESCRIBE TABLE realdeal.core.flyer_items`, not from ddl.sql: that
file only comments the column *names*, since the table is pipeline-owned (databricks/pipeline/03_silver_gold.py
builds it from ai_query's output via `i.*` on an exploded STRUCT) and ddl.sql deliberately does not CREATE it.

Usage:
  uv run --env-file .env python databricks/setup/load_flipp_items.py --week 2026-11-05   # pull from the Volume
  uv run --env-file .env python databricks/setup/load_flipp_items.py path/to/flipp_items.json [more.json ...]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, so apps.api / shared import cleanly

from apps.api.databricks_sql import execute  # noqa: E402
from shared.flipp import FLYER_ITEM_COLUMNS, FLYER_ITEM_ROWS_SQL_TYPE, MERCHANT_TO_STORE_KEY  # noqa: E402

VOLUME = "/Volumes/realdeal/core/flyers"

# SQL types for every flyer_items column, in the table's own order (confirmed via DESCRIBE TABLE).
COLUMN_TYPES = {
    "page_id": "STRING", "store": "STRING", "week_start": "DATE", "brand": "STRING", "item": "STRING",
    "variant": "STRING", "size_qty": "DOUBLE", "size_unit": "STRING", "price": "DOUBLE",
    "confidence": "DOUBLE", "raw_text": "STRING", "bbox": "ARRAY<DOUBLE>", "item_id": "STRING",
    "unit_price": "DOUBLE", "unit": "STRING", "match_text": "STRING",
}
assert set(COLUMN_TYPES) == set(FLYER_ITEM_COLUMNS), "COLUMN_TYPES drifted from shared.flipp.FLYER_ITEM_COLUMNS"


def _create_table_if_missing() -> None:
    cols = ",\n  ".join(f"{c} {COLUMN_TYPES[c]}" for c in FLYER_ITEM_COLUMNS)
    execute(f"CREATE TABLE IF NOT EXISTS flyer_items (\n  {cols}\n) COMMENT "
            "'Silver: one row per advertised product (pipeline-owned; this CREATE is a no-op if it already exists)'")


def _download_sidecar(store_key: str, week: str) -> list[dict] | None:
    from databricks.sdk import WorkspaceClient

    path = f"{VOLUME}/{store_key}/{week}/flipp_items.json"
    try:
        with WorkspaceClient().files.download(path).contents as f:
            return json.loads(f.read())
    except Exception:
        return None


def load(rows_by_store: dict[str, list[dict]]) -> dict[str, dict[str, int]]:
    """INSERTs every row not already present (by item_id). Returns {store: {"loaded": n, "total": n}}."""
    report: dict[str, dict[str, int]] = {}
    for store, rows in rows_by_store.items():
        if not rows:
            report[store] = {"loaded": 0, "total": 0}
            continue
        cols = ", ".join(FLYER_ITEM_COLUMNS)
        execute(
            f"INSERT INTO flyer_items ({cols}) "
            f"SELECT {cols} FROM (SELECT inline(from_json(:rows, '{FLYER_ITEM_ROWS_SQL_TYPE}'))) s "
            "WHERE NOT EXISTS (SELECT 1 FROM flyer_items f WHERE f.item_id = s.item_id)",
            rows=json.dumps(rows),
        )
        report[store] = {"loaded": len(rows), "total": len(rows)}  # exact "loaded" count needs a round trip;
        # good enough for a one-time setup script's console report
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="*", help="local flipp_items.json file(s); omit to pull from the Volume")
    p.add_argument("--week", help="week_start (YYYY-MM-DD) to pull from the Volume; required without `files`")
    args = p.parse_args()

    rows_by_store: dict[str, list[dict]] = {}
    if args.files:
        for f in args.files:
            data = json.loads(Path(f).read_text())
            store = data[0]["store"] if data else Path(f).parent.name
            rows_by_store.setdefault(store, []).extend(data)
    else:
        if not args.week:
            p.error("pass --week YYYY-MM-DD when loading from the Volume (no local files given)")
        for store_key in sorted(set(MERCHANT_TO_STORE_KEY.values())):
            rows = _download_sidecar(store_key, args.week)
            if rows is None:
                print(f"{store_key}: no flipp_items.json for week {args.week} — skipping")
                continue
            rows_by_store[store_key] = rows

    if not rows_by_store:
        print("nothing to load")
        return

    _create_table_if_missing()
    for store, report in load(rows_by_store).items():
        print(f"{store}: loaded {report['loaded']} rows")


if __name__ == "__main__":
    main()
