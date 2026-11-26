from src import tools
from src.tools import TransientError, run_tool


def no_wait(seconds):
    """Used instead of time.sleep so tests run instantly."""
    pass


# ---------- search_docs ----------

def test_search_docs_valid_input():
    r = run_tool("search_docs", {"query": "permission denied"})
    assert r["status"] == "ok"
    assert r["data"]["results"][0]["doc_id"] == "DOC-2"
    assert r["attempts"] == 1


def test_search_docs_invalid_input():
    r = run_tool("search_docs", {"query": "", "top_k": 99})
    assert r["status"] == "error"
    assert r["error"]["type"] == "invalid_input"
    assert r["attempts"] == 0          # rejected before running


def test_search_docs_transient_failure(monkeypatch):
    calls = {"count": 0}

    def flaky_search(args):            # MOCK: fails twice, then works
        calls["count"] += 1
        if calls["count"] < 3:
            raise TransientError("search service unavailable")
        return tools.search_docs(args)

    monkeypatch.setitem(tools.TOOLS, "search_docs", flaky_search)
    r = run_tool("search_docs", {"query": "permission denied"}, sleep=no_wait)
    assert r["status"] == "ok"
    assert calls["count"] == 3
    assert r["attempts"] == 3


# ---------- contracts ----------
def test_every_allowed_tool_has_a_contract():
    for name in tools.ARG_MODELS:
        contract = tools.CONTRACTS[name]
        assert contract["description"]
        assert contract["input"] is tools.ARG_MODELS[name]
        assert contract["output"]
        assert contract["errors"]
