"""Compares ai_query's output in flyer_items against Flipp's flipp_items.json (our structured ground truth)
for the same store/week, and prints field accuracy per store — the 13:00 Sat go/no-go's 85% bar.

There's no shared id between the two sources (ai_query invents its own sha2 hash; Flipp rows use
"flipp-<item id>"), so matching is fuzzy: for each Flipp row, the ai_query row with the highest brand+item+
variant word overlap wins, if it clears a low bar. `compare_rows` is pure and unit-tested with fixtures; only
`main` touches the live workspace.

Usage:
  uv run --env-file .env python databricks/setup/golden_check.py --week 2026-11-05
  uv run --env-file .env python databricks/setup/golden_check.py --week 2026-11-05 --store no_frills
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.api.databricks_sql import query  # noqa: E402
from databricks.setup.load_flipp_items import _download_sidecar  # noqa: E402
from shared.flipp import MERCHANT_TO_STORE_KEY  # noqa: E402
from shared.units import normalize_unit  # noqa: E402

_WORD = re.compile(r"[a-z0-9%]+")
FIELDS = ("brand", "item", "size_qty", "size_unit", "price")
MATCH_FLOOR = 0.5  # looser than logic.MATCH_THRESHOLD: this is "plausibly the same product", not a deal match


def _words(*parts: str | None) -> set[str]:
    return set(_WORD.findall(" ".join(p for p in parts if p).lower()))


def _best_match(flipp_row: dict, ai_rows: list[dict]) -> dict | None:
    want = _words(flipp_row.get("brand"), flipp_row.get("item"), flipp_row.get("variant"))
    if not want:
        return None
    best, best_score = None, 0.0
    for ai in ai_rows:
        have = _words(ai.get("brand"), ai.get("item"), ai.get("variant"), ai.get("raw_text"))
        score = len(want & have) / len(want)
        if score > best_score:
            best, best_score = ai, score
    return best if best_score >= MATCH_FLOOR else None


def _canonical_size(row: dict) -> tuple[float, str] | None:
    """Flipp rows are always normalized to base units (g/ml/ea); ai_query's raw size_qty/size_unit aren't
    guaranteed to be (only its derived unit_price/unit are) — e.g. it might print "1 kg" verbatim. Re-run
    both sides through normalize_unit so "1000 g" and "1 kg" compare equal instead of failing on units alone.
    """
    qty, unit = row.get("size_qty"), row.get("size_unit")
    if qty is None or not unit:
        return None
    return normalize_unit(f"{qty}{unit}")


def _field_agrees(field: str, flipp_row: dict, ai_row: dict) -> bool:
    if field == "price":
        fv, av = flipp_row.get("price"), ai_row.get("price")
        return fv is not None and av is not None and abs(fv - av) <= max(0.5, fv * 0.05)
    if field in ("size_qty", "size_unit"):
        f_size, a_size = _canonical_size(flipp_row), _canonical_size(ai_row)
        if f_size is None or a_size is None:
            return False
        if field == "size_unit":
            return f_size.unit == a_size.unit
        return f_size.unit == a_size.unit and abs(f_size.qty - a_size.qty) <= max(1.0, f_size.qty * 0.1)
    fv, av = flipp_row.get(field), ai_row.get(field)
    return str(fv or "").strip().lower() == str(av or "").strip().lower()


def compare_rows(flipp_rows: list[dict], ai_rows: list[dict]) -> dict:
    """Pure: no I/O. Matched-pair field accuracy, plus coverage (fraction of Flipp rows ai_query also found)."""
    matched, agree = 0, dict.fromkeys(FIELDS, 0)
    for row in flipp_rows:
        best = _best_match(row, ai_rows)
        if best is None:
            continue
        matched += 1
        for f in FIELDS:
            if _field_agrees(f, row, best):
                agree[f] += 1
    total = len(flipp_rows)
    return {
        "total": total,
        "matched": matched,
        "coverage": round(matched / total, 3) if total else 0.0,
        "field_accuracy": {f: round(agree[f] / matched, 3) if matched else 0.0 for f in FIELDS},
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--week", required=True, help="week_start, YYYY-MM-DD")
    p.add_argument("--store", help="one store key; omit to check all five")
    args = p.parse_args()
    stores = [args.store] if args.store else sorted(set(MERCHANT_TO_STORE_KEY.values()))

    overall_matched, overall_total, overall_agree = 0, 0, dict.fromkeys(FIELDS, 0)
    for store in stores:
        flipp_rows = _download_sidecar(store, args.week)
        if flipp_rows is None:
            print(f"{store}: no flipp_items.json for week {args.week} — skipping")
            continue
        ai_rows = query("SELECT * FROM flyer_items WHERE store = :store AND week_start = :week",
                        store=store, week=args.week)
        result = compare_rows(flipp_rows, ai_rows)
        overall_total += result["total"]
        overall_matched += result["matched"]
        for f in FIELDS:
            overall_agree[f] += round(result["field_accuracy"][f] * result["matched"])
        print(f"{store}: {result['matched']}/{result['total']} Flipp rows matched in ai_query's flyer_items "
              f"(coverage {result['coverage']:.0%}); field accuracy among matches: "
              + ", ".join(f"{f}={a:.0%}" for f, a in result["field_accuracy"].items()))

    if overall_matched:
        print("\noverall: " + ", ".join(
            f"{f}={overall_agree[f] / overall_matched:.0%}" for f in FIELDS))
    print(f"overall coverage: {overall_matched}/{overall_total}"
          f" ({overall_matched / overall_total:.0%})" if overall_total else "no rows checked")


if __name__ == "__main__":
    main()
