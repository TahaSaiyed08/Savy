import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "setup"))
import genie_space  # noqa: E402

from apps.api import databricks_sync  # noqa: E402


def _space():
    return json.loads(genie_space.build())


def test_space_reads_the_two_live_tables_and_nothing_else():
    tables = [t["identifier"] for t in _space()["data_sources"]["tables"]]
    assert tables == sorted(tables) == ["realdeal.core.live_listings", "realdeal.core.price_history"]
    assert {databricks_sync.LISTINGS, databricks_sync.HISTORY} == set(tables)


def test_every_example_and_benchmark_query_reads_only_the_tables_it_declares():
    space = _space()
    sqls = ["".join(e["sql"]) for e in space["instructions"]["example_question_sqls"]]
    sqls += ["".join(a["content"]) for q in space["benchmarks"]["questions"] for a in q["answer"]]
    assert len(sqls) >= 4
    for sql in sqls:
        assert sql.lstrip().upper().startswith("SELECT")
        used = set(re.findall(r"realdeal\.core\.\w+", sql))
        assert used and used <= set(genie_space.TABLES)


def test_ids_are_unique_hex_and_each_list_is_in_id_order():
    space = _space()
    lists = [space["config"]["sample_questions"], space["instructions"]["text_instructions"],
             space["instructions"]["example_question_sqls"], space["benchmarks"]["questions"]]
    ids = [i["id"] for lst in lists for i in lst]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids)
    for lst in lists:
        assert [i["id"] for i in lst] == sorted(i["id"] for i in lst)


def test_instructions_teach_genie_the_things_that_make_answers_right():
    text = " ".join(genie_space.INSTRUCTIONS).lower()
    for must in ("postal", "valid_to", "unit_price", "same unit", "price_history", "regular_price"):
        assert must in text
    assert "whole words" in text and "rlike" in text


def test_examples_match_whole_words_without_backslashes_which_spark_reads_as_escapes():
    space = _space()
    sqls = ["".join(e["sql"]) for e in space["instructions"]["example_question_sqls"]]
    eggs = next(q for q in sqls if "price_each" in q)
    assert "RLIKE '(^|[^a-z])eggs?([^a-z]|$)'" in eggs and "price / size_qty" in eggs
    assert not any("\\" in q or "LIKE '%egg%'" in q for q in sqls)  # nothing teaches the substring match or a backslash
    assert "backslash" in " ".join(genie_space.INSTRUCTIONS).lower()


def test_table_comments_exist_for_genie_to_read():
    assert databricks_sync._CREATE_LISTINGS.count("COMMENT") > 20 and "COMMENT" in databricks_sync._CREATE_HISTORY
