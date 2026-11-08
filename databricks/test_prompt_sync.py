"""The ai_query SQL inlines the prompts; this keeps them identical to shared/prompts (one prompt, no drift).

manual matters most: flyer text and the user's typed item must be canonicalized by the same rules to match exactly.
"""
from pathlib import Path

import pytest

from shared import load_prompt

ROOT = Path(__file__).parent


@pytest.mark.parametrize("mode", ["flyer_page", "manual"])
def test_pipeline_prompts_match_shared(mode):
    sql = (ROOT / "pipeline" / "02_extract.sql").read_text()
    prompt = load_prompt(mode).strip()
    assert "'" not in prompt, "single quotes would break the SQL string literal"
    assert f"'{prompt}'" in sql, f"update 02_extract.sql after editing the {mode} prompt in shared/prompts/"
