from pathlib import Path

# The extraction prompts live as versioned markdown files (shared/prompts/<mode>.<version>.md), shared by the API and
# the Databricks pipeline so both read receipts and photos the same way.
PROMPTS = Path(__file__).parent / "prompts"
PROMPT_VERSION = "v1"  # default for modes not in PROMPT_VERSIONS
PROMPT_VERSIONS = {"receipt": "v3", "manual": "v2"}  # per-mode overrides, so tuning one prompt doesn't touch the others


def load_prompt(mode: str, version: str | None = None) -> str:
    """mode in {flyer_page, receipt, product, manual}. Bump a mode by adding a file and a PROMPT_VERSIONS entry."""
    version = version or PROMPT_VERSIONS.get(mode, PROMPT_VERSION)
    return (PROMPTS / f"{mode}.{version}.md").read_text()
