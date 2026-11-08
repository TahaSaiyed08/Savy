"""Databricks SQL Statement Execution API client. Every read has a 5 s timeout and a last-good cache."""
import logging
import os
import time
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
# Reads are wrapped so one slow warehouse can't take the whole app down: each successful result is remembered, and if
# the same read later times out or errors, the remembered answer is served (with a warning in the log).
_last_good: OrderedDict[tuple, list[dict]] = OrderedDict()  # LRU: keys include user ids, so bound it
_MAX_CACHED = 2000
# Python type -> SQL parameter type. Anything not listed (strings, UUIDs, None) is sent as a STRING parameter.
_TYPES = {bool: "BOOLEAN", int: "BIGINT", float: "DOUBLE", datetime: "TIMESTAMP", date: "DATE"}


# One client for the life of the process, shared by every request and by refine.py and genie.py.
@cache
def _client() -> WorkspaceClient:
    return WorkspaceClient()  # reads DATABRICKS_HOST / DATABRICKS_TOKEN


# Values never get pasted into the SQL text: they travel as named parameters (:name), which is what keeps every
# statement in store.py a fixed literal and closes off SQL injection.
def _params(params: dict) -> list[StatementParameterListItem]:
    return [StatementParameterListItem(name=k, value=None if v is None else str(v), type=_TYPES.get(type(v), "STRING"))
            for k, v in params.items()]


def _rows(r) -> list[dict]:
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"statement {r.status.state}: {r.status.error}")
    if not r.manifest or not r.manifest.schema.columns:
        return []
    # The API returns rows as bare lists of strings plus a separate schema; zip them into dicts keyed by column name.
    cols = [c.name for c in r.manifest.schema.columns]
    return [dict(zip(cols, row, strict=True)) for row in (r.result.data_array or [])]


def _run(sql: str, params: dict) -> list[dict]:
    r = _client().statement_execution.execute_statement(
        statement=sql,
        warehouse_id=os.environ["DATABRICKS_WAREHOUSE_ID"],
        catalog="realdeal",
        schema="core",
        parameters=_params(params),
        # A request path must never hang on the warehouse: wait 5 s, and if it isn't done, cancel it.
        wait_timeout="5s",
        on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CANCEL,
    )
    return _rows(r)


def run_long(sql: str, timeout: float = 90.0, **params) -> list[dict]:
    """For slow statements such as ai_query on an image: polls up to `timeout` seconds, then cancels.

    Never cached, and outside the 5 s budget of query()/execute(), which stays the rule for everything else.
    """
    # Unlike _run, this lets a statement keep running after the first 50 s and polls for it, for slow AI queries.
    w, deadline = _client(), time.monotonic() + timeout
    r = w.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=os.environ["DATABRICKS_WAREHOUSE_ID"],
        catalog="realdeal",
        schema="core",
        parameters=_params(params),
        wait_timeout="50s",
        on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
    )
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.monotonic() > deadline:
            w.statement_execution.cancel_execution(r.statement_id)
            raise TimeoutError(f"statement still running after {timeout:.0f} s; cancelled")
        time.sleep(1)
        r = w.statement_execution.get_statement(r.statement_id)
    return _rows(r)


def query(sql: str, fallback: bool = True, **params) -> list[dict]:
    """Read. Falls back to the last good result for the same query if Databricks is slow or down.

    fallback=False for reads right after a write: a stale answer there would undo the write in the user's eyes.
    """
    # The cache key is the statement plus its parameters, so each user's own list is cached separately.
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
