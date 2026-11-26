import json
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

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
# ---------- Running a tool safely ----------

class TransientError(Exception):
    """A temporary failure (service down, network). Worth retrying."""


class ToolError(Exception):
    """A permanent failure (e.g. order not found). Retrying will not help."""

    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


TOOLS = {
    "search_docs": search_docs,
}


def call_with_timeout(func, args, timeout):
    """Run func(args), but stop waiting after `timeout` seconds (raises TimeoutError)."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(func, args).result(timeout=timeout)
    finally:
        pool.shutdown(wait=False)


def run_tool(name, raw_args, retries=2, timeout=5.0, sleep=time.sleep):
    """Check the request, run the tool with retries, and always return a structured result."""
    start = time.monotonic()

    def finish(result, attempts):
        result["attempts"] = attempts
        result["latency_ms"] = round((time.monotonic() - start) * 1000)
        return result

    args, problem = check(name, raw_args)
    if problem:
        return finish(problem, 0)          # rejected: the tool never ran

    for attempt in range(1, retries + 2):
        try:
            data = call_with_timeout(TOOLS[name], args, timeout)
            return finish(ok(data), attempt)
        except ToolError as e:
            return finish(err(e.error_type, e.message), attempt)    # permanent: no retry
        except TimeoutError:
            last_type = "timeout"
        except TransientError:
            last_type = "service_unavailable"
        except Exception:
            return finish(err("internal_error", f"{name} failed unexpectedly"), attempt)

        if attempt <= retries:
            sleep(0.5 * 2 ** (attempt - 1))  # wait 0.5s, then 1s, ...

    return finish(err(last_type, f"{name} failed after {retries + 1} attempts"), retries + 1)
