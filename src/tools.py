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
