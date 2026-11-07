"""Shared upload step: flyer page images -> /Volumes/realdeal/core/flyers/<store>/<week_start>/<page_no>.jpg.

Runs on a laptop or in FastAPI, not in a notebook: Free Edition compute cannot reach store websites.
Auth comes from DATABRICKS_HOST / DATABRICKS_TOKEN.
"""
import io
import sys
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

VOLUME = "/Volumes/realdeal/core/flyers"


def week_start(today: date | None = None) -> date:
    """BC flyers flip on Thursday."""
    today = today or date.today()
    return today - timedelta(days=(today.weekday() - 3) % 7)


def upload_pages(store: str, pages: list[bytes], week: date | None = None) -> list[str]:
    from databricks.sdk import WorkspaceClient

    w, week = WorkspaceClient(), week or week_start()
    paths = []
    for n, img in enumerate(pages, 1):
        path = f"{VOLUME}/{store}/{week.isoformat()}/{n:03d}.jpg"
        w.files.upload(path, io.BytesIO(img), overwrite=True)
        paths.append(path)
    return paths


def run(store: str, fetch: Callable[[], list[bytes]]) -> None:
    """CLI: python databricks/fetchers/<store>.py [--from-dir DIR]

    --from-dir uploads screenshots you saved by hand: the 10:00 go/no-go fallback if scraping fails.
    """
    if sys.argv[1:2] == ["--from-dir"]:
        files = sorted(p for p in Path(sys.argv[2]).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        pages = [p.read_bytes() for p in files]
    else:
        pages = fetch()
    print("\n".join(upload_pages(store, pages)) or "no pages")
