import uuid
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from apps.api import databricks_sql, genie, main
from apps.api.main import app

c = TestClient(app)
H = {"X-User-Id": str(uuid.uuid4())}


def _message(text="Safeway has the cheapest milk.", with_query=True, error=None):
    query = NS(query="SELECT 1", description="Cheapest milk")
    attachments = [NS(text=NS(content=text), query=None, attachment_id="t")]
    if with_query:
        attachments.append(NS(text=None, query=query, attachment_id="q"))
    return NS(conversation_id="conv-1", message_id="msg-1", attachments=attachments, error=error)


class FakeGenie:
    def __init__(self, message=None, boom=None):
        self.message, self.boom, self.calls = message or _message(), boom, []

    def start_conversation_and_wait(self, space, content, *, timeout):
        self.calls.append(("start", space, content, timeout))
        if self.boom:
            raise self.boom
        return self.message

    def create_message_and_wait(self, space, conversation, content, *, timeout):
        self.calls.append(("follow", space, conversation, content))
        if self.boom:
            raise self.boom
        return self.message

    def get_message_attachment_query_result(self, space, conversation, message, attachment):
        self.calls.append(("result", attachment))
        columns = [NS(name="store"), NS(name="price")]
        rows = [["Safeway", "5.99"], ["No Frills", None]] + [["x", "1"]] * 30
        return NS(statement_response=NS(manifest=NS(schema=NS(columns=columns)), result=NS(data_array=rows)))


@pytest.fixture
def fake(monkeypatch, tmp_path):
    f = FakeGenie()
    monkeypatch.setattr(databricks_sql, "_client", lambda: NS(genie=f))
    monkeypatch.setattr(genie, "SPACE_FILE", tmp_path / "genie_space.json")
    monkeypatch.setenv("GENIE_SPACE_ID", "space-1")
    for k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(main, "_ask_hits", {})
    return f


def test_ask_returns_the_answer_the_sql_and_a_capped_table(fake):
    got = genie.ask("cheapest milk?", "V6T1Z4")
    assert (got.answer, got.sql, got.description, got.conversation_id) == (
        "Safeway has the cheapest milk.", "SELECT 1", "Cheapest milk", "conv-1")
    assert got.columns == ["store", "price"] and got.rows[:2] == [["Safeway", "5.99"], ["No Frills", None]]
    assert len(got.rows) == genie.MAX_ROWS
    kind, space, content, timeout = fake.calls[0]
    assert (kind, space, timeout) == ("start", "space-1", genie.TIMEOUT)
    assert "postal = 'V6T1Z4'" in content and content.endswith("cheapest milk?")


def test_a_follow_up_continues_the_same_conversation(fake):
    genie.ask("and eggs?", "V6T1Z4", "conv-1")
    assert fake.calls[0][:3] == ("follow", "space-1", "conv-1")


def test_an_answer_with_words_only_has_no_table(fake):
    fake.message = _message(with_query=False)
    got = genie.ask("hello", "V6T1Z4")
    assert got.answer and got.sql is None and got.rows == [] and got.columns == []


def test_failures_become_messages_safe_to_show(fake):
    fake.boom = TimeoutError()
    with pytest.raises(genie.GenieError, match="too long"):
        genie.ask("q", "V6T1Z4")
    fake.boom = RuntimeError("secret internal detail")
    with pytest.raises(genie.GenieError) as e:
        genie.ask("q", "V6T1Z4")
    assert "secret" not in str(e.value)
    fake.boom, fake.message = None, _message(error=NS(error="x"))
    with pytest.raises(genie.GenieError):
        genie.ask("q", "V6T1Z4")


def test_space_id_comes_from_the_environment_or_the_saved_file(fake, monkeypatch):
    assert genie.space_id() == "space-1"
    monkeypatch.delenv("GENIE_SPACE_ID")
    assert genie.space_id() is None and not genie.available()
    genie.SPACE_FILE.write_text('{"space_id": "from-file"}')
    assert genie.space_id() == "from-file" and genie.available()


def test_endpoint_answers_validates_and_reports_missing_setup(fake, monkeypatch):
    r = c.post("/ask", headers={**H, "X-Postal-Code": "v6t 1z4"}, json={"question": "cheapest milk?"})
    assert r.status_code == 200 and r.json()["answer"] and r.json()["rows"][0] == ["Safeway", "5.99"]
    assert "postal = 'V6T1Z4'" in fake.calls[0][2]  # normalized before it reaches Genie
    assert c.post("/ask", json={"question": "x"}).status_code == 422  # too short
    assert c.post("/ask", json={"question": "milk?"}, headers={"X-Postal-Code": "x'; drop"}).status_code == 422
    fake.boom = RuntimeError("down")
    assert c.post("/ask", json={"question": "milk?"}).status_code == 502
    monkeypatch.delenv("GENIE_SPACE_ID")
    assert c.post("/ask", json={"question": "milk?"}).status_code == 503


def test_status_says_whether_ask_is_ready(fake, monkeypatch):
    assert c.get("/flyers/status").json()["ask_enabled"] is True
    monkeypatch.delenv("GENIE_SPACE_ID")
    assert c.get("/flyers/status").json()["ask_enabled"] is False


def test_asking_is_rate_limited_per_client(fake, monkeypatch):
    monkeypatch.setattr(main, "ASK_LIMIT", 2)
    codes = [c.post("/ask", json={"question": "milk?"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
