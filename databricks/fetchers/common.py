"""Shared upload step: flyer page images -> /Volumes/realdeal/core/flyers/<store>/<week_start>/<page_no>.jpg.

Runs on a laptop or in FastAPI, not in a notebook: Free Edition compute cannot reach store websites.
Auth comes from DATABRICKS_HOST / DATABRICKS_TOKEN.
"""
import io
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# Direct script execution (`python databricks/fetchers/x.py`) only puts this file's own directory on
# sys.path, not the repo root, so `from shared import flipp` would fail otherwise. Every fetcher imports
# this module first, so fixing it here covers all of them.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

VOLUME = "/Volumes/realdeal/core/flyers"


def week_start(today: date | None = None) -> date:
    """BC flyers flip on Thursday."""
    today = today or date.today()
    return today - timedelta(days=(today.weekday() - 3) % 7)


@dataclass
class FetchResult:
    """What a store's fetch() returns when it has more than just page images to upload."""

    pages: list[bytes]
    week: date
    items: list[dict] | None = None  # structured rows for the flipp_items.json sidecar, if any


def upload_pages(store: str, pages: list[bytes], week: date | None = None) -> list[str]:
    from databricks.sdk import WorkspaceClient

    w, week = WorkspaceClient(), week or week_start()
    paths = []
    for n, img in enumerate(pages, 1):
        path = f"{VOLUME}/{store}/{week.isoformat()}/{n:03d}.jpg"
        w.files.upload(path, io.BytesIO(img), overwrite=True)
        paths.append(path)
    return paths


def upload_items_sidecar(store: str, week: date, items: list[dict]) -> str:
    """flyers/<store>/<week_start>/flipp_items.json: structured rows (golden set + ai_query fallback)."""
    from databricks.sdk import WorkspaceClient

    path = f"{VOLUME}/{store}/{week.isoformat()}/flipp_items.json"
    WorkspaceClient().files.upload(path, io.BytesIO(json.dumps(items, indent=2).encode()), overwrite=True)
    return path


def run(store: str, fetch: Callable[[], list[bytes] | FetchResult]) -> None:
    """CLI: python databricks/fetchers/<store>.py [--from-dir DIR]

    --from-dir uploads screenshots you saved by hand: the 10:00 go/no-go fallback if scraping fails.
    """
    if sys.argv[1:2] == ["--from-dir"]:
        files = sorted(p for p in Path(sys.argv[2]).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        pages = [p.read_bytes() for p in files]
        print("\n".join(upload_pages(store, pages)) or "no pages")
        return

    result = fetch()
    if isinstance(result, FetchResult):
        paths = upload_pages(store, result.pages, result.week)
        if result.items:
            paths.append(upload_items_sidecar(store, result.week, result.items))
        print("\n".join(paths) or "no pages")
    else:  # plain list[bytes]: legacy contract, still supported
        print("\n".join(upload_pages(store, result)) or "no pages")
