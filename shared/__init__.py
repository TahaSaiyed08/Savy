from pathlib import Path

PROMPTS = Path(__file__).parent / "prompts"
PROMPT_VERSION = "v1"


def load_prompt(mode: str, version: str = PROMPT_VERSION) -> str:
    """mode in {flyer_page, receipt, product, manual}. Bump the version by adding a new file."""
    return (PROMPTS / f"{mode}.{version}.md").read_text()
