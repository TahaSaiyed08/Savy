"""Ask Genie, the Databricks AI/BI space over the live flyer tables, a question in plain words.

Genie turns the question into SQL over realdeal.core.live_listings and price_history, runs it on the warehouse and
explains the result. The space is made once by databricks/setup/create_genie_space.py, which saves its id where
space_id() finds it.
"""
import json
import logging
import os
from datetime import timedelta
from pathlib import Path

from apps.api.models import AskResponse

log = logging.getLogger(__name__)

SPACE_FILE = Path(__file__).parent / "data" / "genie_space.json"
TIMEOUT = timedelta(seconds=150)  # a cold serverless warehouse takes a while to start
MAX_ROWS = 15
_NEEDS = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID")


class GenieError(RuntimeError):
    """Genie could not answer; the message is safe to show."""


def space_id() -> str | None:
    if os.getenv("GENIE_SPACE_ID"):
        return os.environ["GENIE_SPACE_ID"]
    try:
        return json.loads(SPACE_FILE.read_text()).get("space_id")
    except (OSError, ValueError):
        return None


def available() -> bool:
    return bool(space_id()) and all(os.getenv(k) for k in _NEEDS)


def ask(question: str, postal: str, conversation_id: str | None = None) -> AskResponse:
    from apps.api import databricks_sql as db

    w, sid = db._client(), space_id()
    if not sid:
        raise GenieError("Genie isn't set up yet")
    # The postal code is validated by the API before it gets here, so this line can't carry anything else.
    content = f"The shopper's postal code is {postal}: only use rows where postal = '{postal}'. {question}"
    try:
        if conversation_id:
            msg = w.genie.create_message_and_wait(sid, conversation_id, content, timeout=TIMEOUT)
        else:
            msg = w.genie.start_conversation_and_wait(sid, content, timeout=TIMEOUT)
    except TimeoutError as e:
        raise GenieError("Genie took too long. Try again in a moment.") from e
    except Exception as e:
        log.warning("Genie failed", exc_info=True)
        raise GenieError("Genie couldn't answer that. Try asking it another way.") from e
    if msg.error:
        raise GenieError("Genie couldn't answer that. Try asking it another way.")

    out = AskResponse(conversation_id=msg.conversation_id)
    for a in msg.attachments or []:
        if a.text and a.text.content:
            out.answer = a.text.content
        if a.query:
            out.sql, out.description = a.query.query, a.query.description
            try:
                res = w.genie.get_message_attachment_query_result(
                    sid, msg.conversation_id, msg.message_id, a.attachment_id)
            except Exception:
                log.warning("couldn't read Genie's result table", exc_info=True)
                continue
            sr = res.statement_response
            if sr and sr.manifest and sr.manifest.schema and sr.manifest.schema.columns:
                out.columns = [c.name for c in sr.manifest.schema.columns]
            if sr and sr.result and sr.result.data_array:
                out.rows = [[None if v is None else str(v) for v in row] for row in sr.result.data_array[:MAX_ROWS]]
    return out
