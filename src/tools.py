import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

DATA = Path(__file__).parent.parent / "data"

"""Tools for the Bug Investigator agent, and the code that runs them safely."""


def ok(data):
    """A successful tool result."""
    return {"status": "ok", "data": data}


def err(error_type, message, retryable=False):
    """A failed tool result. Never contains secrets or stack traces."""
    return {
        "status": "error",
        "error": {
            "type": error_type,
            "message": message,
            "retryable": retryable,
        },
    }
# ---------- Contracts: which arguments each tool accepts ----------

class SearchDocsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=2, max_length=200)
    top_k: int = Field(default=3, ge=1, le=5)


ARG_MODELS = {
    "search_docs": SearchDocsArgs,
}


# ---------- Check: runs BEFORE any tool is executed ----------

def check(name, raw_args):
    """Return (args, None) if the request is allowed and valid, or (None, error)."""
    if name not in ARG_MODELS:
        return None, err("permission_denied", f"Tool '{name}' is not allowed")
    if not isinstance(raw_args, dict):
        return None, err("invalid_input", "Arguments must be a JSON object")
    try:
        args = ARG_MODELS[name](**raw_args)
    except ValidationError as e:
        problems = "; ".join(f"{p['loc'][0]}: {p['msg']}" for p in e.errors())
        return None, err("invalid_input", problems)
    return args, None
# ---------- The tools themselves ----------

def load_data(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


STOP_WORDS = {"the", "and", "for", "with", "not", "can", "why", "how", "what", "does"}


def words(text):
    """Lowercase words of 3+ letters, without common filler words."""
    return {w for w in re.findall(r"[a-z0-9_]+", text.lower()) if len(w) >= 3 and w not in STOP_WORDS}


def search_docs(args):
    """Return the support documents that share the most words with the query."""
    query_words = words(args.query)
    results = []
    for doc in load_data("docs.json"):
        score = len(query_words & words(doc["title"] + " " + doc["content"]))
        if score > 0:
            results.append({"doc_id": doc["id"], "title": doc["title"],
                            "content": doc["content"], "score": score})
    results.sort(key=lambda r: r["score"], reverse=True)
    return {"results": results[: args.top_k]}
