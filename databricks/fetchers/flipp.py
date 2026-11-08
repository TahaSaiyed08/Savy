"""Step 0: this week's flyer for every store, from Flipp's public JSON, to <store>/<week_start>/flipp.jsonl.

Flipp gives what OCR can't: each item's exact tile on its page, its price, the flyer's valid dates and a cutout
image of the tile. The pipeline only asks ai_query to split the printed text into brand / item / variant / size.

Usage: uv run --env-file .env python databricks/fetchers/flipp.py [store ...] [--limit N] [--dry-run DIR]
       (no stores = all five; --dry-run writes the .jsonl files to DIR instead of the Volume)

Auto Loader skips a file it has already read, so re-fetching the same week (same path) needs
`databricks bundle run realdeal_flyers --full-refresh flipp_items,flipp_extractions,flyer_items`.
"""
import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from common import upload  # noqa: E402

API = "https://backflipp.wishabi.com/flipp"
POSTAL = "V6T1Z4"  # UBC
MERCHANTS = {  # Volume slug (shared/stores.py) -> Flipp merchant name
    "save_on_foods": "Save-On-Foods",
    "superstore": "Real Canadian Superstore",
    "no_frills": "No Frills",
    "safeway": "Safeway",
    "tnt": "T&T Supermarket",
}
_MULTI = re.compile(r"^\s*(\d+)\s*(?:/|for\b)", re.I)  # pre_price_text "2/" or "2 for": price is for n units
http = httpx.Client(timeout=20, headers={"User-Agent": "realdeal-hackathon/0.1"}, follow_redirects=True)


def _get(path: str, **params) -> dict:
    r = http.get(f"{API}/{path}", params=params)
    r.raise_for_status()
    return r.json()


def grocery_flyers() -> dict[str, dict]:
    """slug -> the merchant's current grocery flyer (skips toy books and decor flyers)."""
    flyers = _get("flyers", locale="en-ca", postal_code=POSTAL)["flyers"]
    by_name = {v: k for k, v in MERCHANTS.items()}
    out = {}
    for f in flyers:
        slug = by_name.get(f["merchant"])
        if slug and "Groceries" in f.get("categories_csv", "") and (slug not in out or f["width"] > out[slug]["width"]):
            out[slug] = f
    return out


def _price(*candidates) -> float | None:
    for c in candidates:
        try:
            return round(float(c), 2)
        except (TypeError, ValueError):
            continue
    return None


def rows(slug: str, flyer: dict, limit: int | None = None) -> list[dict]:
    data = _get(f"flyers/{flyer['id']}")
    pages = sorted(data["pages"], key=lambda p: p["left"])
    items = [i for i in data["items"] if i.get("display_type") == 1][:limit]
    with ThreadPoolExecutor(max_workers=8) as pool:
        details = list(pool.map(lambda i: _get(f"items/{i['id']}").get("item", {}), items))
    week = flyer["valid_from"][:10]
    out = []
    for i, d in zip(items, details, strict=True):
        cx = (i["left"] + i["right"]) / 2
        page = next((p for p in pages if p["left"] <= cx < p["right"]), None)
        if page is None:
            continue
        w, h = page["right"] - page["left"], page["top"] - page["bottom"]
        bbox = [(i["left"] - page["left"]) / w, (page["top"] - i["top"]) / h,
                (i["right"] - page["left"]) / w, (page["top"] - i["bottom"]) / h]
        price = _price(d.get("current_price"), i.get("price"))
        m = _MULTI.match(d.get("pre_price_text") or "")
        multi = bool(m) and int(m[1]) > 1
        if price and multi:
            price = round(price / int(m[1]), 2)
        # The per-unit price replaces "2/ $7.50" in the text, else ai_query reads "2/" as a 2-pack and doubles the size.
        text = [i.get("brand"), i.get("name"), d.get("description"), None if multi else d.get("pre_price_text"),
                f"${price}" if price else None, d.get("price_text")]
        out.append({
            "flipp_id": str(i["id"]), "store": slug, "week_start": week,
            "valid_from": flyer["valid_from"][:10], "valid_to": flyer["valid_to"][:10],
            "page_id": f"flipp-{flyer['id']}-{page['page']}", "page_no": page["page"], "page_aspect": round(w / h, 4),
            "bbox": [round(min(max(v, 0.0), 1.0), 4) for v in bbox],
            "image_url": (i.get("cutout_image_url") or "").replace("http://", "https://", 1) or None,
            "price": price, "raw_text": " ".join(str(t) for t in text if t)[:300],
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stores", nargs="*", help=", ".join(MERCHANTS))
    ap.add_argument("--limit", type=int, help="items per flyer, for a cheap first test run")
    ap.add_argument("--dry-run", type=Path, metavar="DIR")
    a = ap.parse_args()
    if bad := set(a.stores) - set(MERCHANTS):
        ap.error(f"unknown store {', '.join(bad)}; choose from {', '.join(MERCHANTS)}")
    flyers = grocery_flyers()
    for slug in a.stores or MERCHANTS:
        if slug not in flyers:
            print(f"{slug}: no grocery flyer on Flipp for {POSTAL}", file=sys.stderr)
            continue
        r = rows(slug, flyers[slug], a.limit)
        if not r:
            print(f"{slug}: flyer {flyers[slug]['id']} has no items", file=sys.stderr)
            continue
        body, path = "".join(json.dumps(x) + "\n" for x in r).encode(), f"{slug}/{r[0]['week_start']}/flipp.jsonl"
        if a.dry_run:
            (a.dry_run / path).parent.mkdir(parents=True, exist_ok=True)
            (a.dry_run / path).write_bytes(body)
            print(f"{len(r):4d} items  {a.dry_run / path}")
        else:
            print(f"{len(r):4d} items  {upload(path, body)}")


if __name__ == "__main__":
    main()
