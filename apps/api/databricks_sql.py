"""Databricks SQL Statement Execution API client. Every read has a 5 s timeout and a last-good cache."""
import logging
import os
from collections import OrderedDict
from datetime import date, datetime
from functools import cache

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import (
    ExecuteStatementRequestOnWaitTimeout,
    StatementParameterListItem,
    StatementState,
)

log = logging.getLogger(__name__)
_last_good: OrderedDict[tuple, list[dict]] = OrderedDict()  # LRU: keys include user ids, so bound it
_MAX_CACHED = 2000
_TYPES = {bool: "BOOLEAN", int: "BIGINT", float: "DOUBLE", datetime: "TIMESTAMP", date: "DATE"}


@cache
def _client() -> WorkspaceClient:
    return WorkspaceClient()  # reads DATABRICKS_HOST / DATABRICKS_TOKEN


def _run(sql: str, params: dict) -> list[dict]:
    r = _client().statement_execution.execute_statement(
        statement=sql,
        warehouse_id=os.environ["DATABRICKS_WAREHOUSE_ID"],
        catalog="realdeal",
        schema="core",
        parameters=[
            StatementParameterListItem(
                name=k, value=None if v is None else str(v), type=_TYPES.get(type(v), "STRING")
            )
            for k, v in params.items()
        ],
        wait_timeout="5s",
        on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CANCEL,
    )
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"statement {r.status.state}: {r.status.error}")
    if not r.manifest or not r.manifest.schema.columns:
        return []
    cols = [c.name for c in r.manifest.schema.columns]
    return [dict(zip(cols, row, strict=True)) for row in (r.result.data_array or [])]


def query(sql: str, fallback: bool = True, **params) -> list[dict]:
    """Read. Falls back to the last good result for the same query if Databricks is slow or down.

    fallback=False for reads right after a write: a stale answer there would undo the write in the user's eyes.
    """
    key = (sql, tuple(sorted(params.items())))
    try:
        _last_good[key] = rows = _run(sql, params)
        _last_good.move_to_end(key)
        if len(_last_good) > _MAX_CACHED:
            _last_good.popitem(last=False)
        return rows
    except Exception:
        if fallback and key in _last_good:
            log.warning("serving cached result for %s", sql[:60], exc_info=True)
            return _last_good[key]
        raise


def execute(sql: str, **params) -> None:
    """Write. Never cached: a failed write must surface, not be papered over."""
    _run(sql, params)
