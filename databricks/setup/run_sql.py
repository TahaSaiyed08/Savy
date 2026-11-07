"""Run a .sql file (or -e "SQL") on the team warehouse via the SQL Statement API, in realdeal.core.

Usage: uv run --env-file .env python databricks/setup/run_sql.py databricks/sql/views.sql
       uv run --env-file .env python databricks/setup/run_sql.py -e "SELECT count(*) FROM flyer_items"

Strips -- comments and splits on ; (both quote-aware), skips USE lines (catalog/schema are passed instead),
runs statements in order, stops at the first failure, and prints rows for statements that return any.
"""
import os
import sys
import time

USE_PREFIX = "use "


def statements(sql: str) -> list[str]:
    out, cur, i, quote = [], [], 0, None
    while i < len(sql):
        ch = sql[i]
        if quote:
            cur.append(ch)
            if ch == quote:
                if sql[i + 1 : i + 2] == quote:  # '' escape
                    cur.append(sql[i + 1])
                    i += 1
                else:
                    quote = None
        elif ch in "'\"`":
            quote = ch
            cur.append(ch)
        elif sql.startswith("--", i):
            while i < len(sql) and sql[i] != "\n":
                i += 1
            continue
        elif ch == ";":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    stmts = [s.strip() for s in out]
    return [s for s in stmts if s and not s.lower().startswith(USE_PREFIX)]


def run(stmt: str):
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout, StatementState

    w = WorkspaceClient()
    r = w.statement_execution.execute_statement(
        statement=stmt, warehouse_id=os.environ["DATABRICKS_WAREHOUSE_ID"], catalog="realdeal", schema="core",
        wait_timeout="50s", on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
    )
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise SystemExit(f"FAILED ({r.status.state}): {r.status.error.message if r.status.error else ''}")
    return r


def main() -> None:
    sql = sys.argv[2] if sys.argv[1:2] == ["-e"] else open(sys.argv[1]).read()
    for n, stmt in enumerate(statements(sql), 1):
        print(f"[{n}] {stmt.splitlines()[0][:100]}")
        r = run(stmt)
        if r.manifest and r.manifest.schema and r.manifest.schema.columns and r.result and r.result.data_array:
            print("    " + " | ".join(c.name for c in r.manifest.schema.columns))
            for row in r.result.data_array[:50]:
                print("    " + " | ".join("NULL" if v is None else str(v)[:200] for v in row))
        print("    ok")


if __name__ == "__main__":
    main()
