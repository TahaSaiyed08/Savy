"""Upload to the flyers Volume: /Volumes/realdeal/core/flyers/<store>/<week_start>/...

Runs on a laptop, not in a notebook: Free Edition compute cannot reach store websites.
Auth comes from DATABRICKS_HOST / DATABRICKS_TOKEN.

Page images you saved by hand (e.g. a PDF flyer split into JPGs) go through the vision ai_query:
    uv run --env-file .env python databricks/fetchers/common.py save_on_foods ~/flyer-shots [2026-11-05]
"""
import io
import sys
from datetime import date, timedelta
from pathlib import Path

VOLUME = "/Volumes/realdeal/core/flyers"


def week_start(today: date | None = None) -> date:
    """BC flyers flip on Thursday."""
    today = today or date.today()
    return today - timedelta(days=(today.weekday() - 3) % 7)


def upload(path: str, data: bytes) -> str:
    from databricks.sdk import WorkspaceClient

    WorkspaceClient().files.upload(f"{VOLUME}/{path}", io.BytesIO(data), overwrite=True)
    return f"{VOLUME}/{path}"


if __name__ == "__main__":
    store, folder = sys.argv[1], Path(sys.argv[2])
    week = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else week_start()
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    for n, f in enumerate(files, 1):
        print(upload(f"{store}/{week.isoformat()}/{n:03d}{f.suffix.lower()}", f.read_bytes()))
