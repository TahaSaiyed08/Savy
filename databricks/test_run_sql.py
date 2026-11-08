import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "setup"))
from run_sql import statements  # noqa: E402


def test_splits_and_strips_comments_but_not_inside_strings():
    sql = """
    -- header comment
    USE realdeal.core;
    CREATE VIEW v AS SELECT 'a;b' AS x, 'it''s -- fine' AS y; -- trailing
    use catalog realdeal;
    SELECT 1
    """
    assert statements(sql) == ["CREATE VIEW v AS SELECT 'a;b' AS x, 'it''s -- fine' AS y", "SELECT 1"]


def test_real_files_parse():
    root = Path(__file__).parent / "sql"
    assert len(statements((root / "views.sql").read_text())) == 1
    # catalog, schema, 2 volumes, 4 tables, 1 ALTER (in_basket); USE dropped
    assert len(statements((root / "ddl.sql").read_text())) == 9
