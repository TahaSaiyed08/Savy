"""The ai_query SQL inlines the flyer prompt; this keeps it identical to shared/prompts (one prompt, no drift)."""
from pathlib import Path

from shared import load_prompt

ROOT = Path(__file__).parent


def test_flyer_prompt_matches_shared():
    sql = (ROOT / "pipeline" / "02_extract.sql").read_text()
    prompt = load_prompt("flyer_page").strip()
    assert "'" not in prompt, "single quotes would break the SQL string literal"
    assert f"'{prompt}'" in sql, "regenerate 02_extract.sql after editing shared/prompts/flyer_page.v1.md"
