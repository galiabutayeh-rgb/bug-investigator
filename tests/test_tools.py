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

# ---------- get_order_history ----------

def test_order_history_valid_input():
    r = run_tool("get_order_history", {"order_id": "104"})
    assert r["status"] == "ok"
    ids = [rec["id"] for rec in r["data"]["records"]]
    assert ids == ["H-104-1", "H-104-2"]


def test_order_history_invalid_input():
    r = run_tool("get_order_history", {"order_id": "104; delete"})
    assert r["error"]["type"] == "invalid_input"
    assert r["attempts"] == 0


def test_order_history_unknown_order_is_not_retried():
    r = run_tool("get_order_history", {"order_id": "999"}, sleep=no_wait)
    assert r["error"]["type"] == "not_found"
    assert r["attempts"] == 1


def test_order_history_transient_failure(monkeypatch):
    calls = {"count": 0}

    def flaky_history(args):           # MOCK: fails twice, then works
        calls["count"] += 1
        if calls["count"] < 3:
            raise TransientError("history service unavailable")
        return tools.get_order_history(args)

    monkeypatch.setitem(tools.TOOLS, "get_order_history", flaky_history)
    r = run_tool("get_order_history", {"order_id": "104"}, sleep=no_wait)
    assert r["status"] == "ok"
    assert calls["count"] == 3
# ---------- check_permissions ----------
def test_permissions_valid_input():
    r = run_tool("check_permissions", {"user_id": "avi", "action": "edit_order"})
    assert r["status"] == "ok"
    assert r["data"]["role"] == "viewer"
    assert r["data"]["allowed"] is False
    assert r["data"]["rule_id"] == "ROLE-viewer"


def test_permissions_invalid_input():
    r = run_tool("check_permissions", {"user_id": "avi"})          # action is missing
    assert r["error"]["type"] == "invalid_input"
    assert r["attempts"] == 0


def test_permissions_unknown_user_is_not_retried():
    r = run_tool("check_permissions", {"user_id": "ghost", "action": "edit_order"}, sleep=no_wait)
    assert r["error"]["type"] == "not_found"
    assert r["attempts"] == 1


def test_permissions_transient_failure(monkeypatch):
    calls = {"count": 0}

    def flaky_permissions(args):       # MOCK: fails twice, then works
        calls["count"] += 1
        if calls["count"] < 3:
            raise TransientError("permissions service unavailable")
        return tools.check_permissions(args)

    monkeypatch.setitem(tools.TOOLS, "check_permissions", flaky_permissions)
    r = run_tool("check_permissions", {"user_id": "dana", "action": "edit_order"}, sleep=no_wait)
    assert r["status"] == "ok"
    assert r["data"]["allowed"] is True
    assert calls["count"] == 3
