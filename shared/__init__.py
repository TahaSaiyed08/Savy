from pathlib import Path

PROMPTS = Path(__file__).parent / "prompts"
PROMPT_VERSION = "v1"  # default for modes not in PROMPT_VERSIONS
PROMPT_VERSIONS = {"receipt": "v2", "manual": "v2"}  # per-mode overrides, so tuning one prompt doesn't touch the others


def load_prompt(mode: str, version: str | None = None) -> str:
    """mode in {flyer_page, receipt, product, manual}. Bump a mode by adding a file and a PROMPT_VERSIONS entry."""
    version = version or PROMPT_VERSIONS.get(mode, PROMPT_VERSION)
    return (PROMPTS / f"{mode}.{version}.md").read_text()
