"""Agent RPC protocol: status codes + JSON envelope."""
from __future__ import annotations

from typing import Any, Dict, Optional

# Semantic status codes used by the VocaForge Agent RPC.
NOT_FOUND = 404  # model not found in registry
LOADED = 103  # model found and loaded (DiffSinger-style "early hints")
OK = 200  # success (e.g. synthesis finished)
BAD_REQUEST = 400  # malformed request
ERROR = 500  # internal error

_CODE_MESSAGES = {
    NOT_FOUND: "model not found",
    LOADED: "model found and loaded",
    OK: "ok",
    BAD_REQUEST: "bad request",
    ERROR: "internal error",
}


def envelope(
    code: int, message: Optional[str] = None, data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message or _CODE_MESSAGES.get(code, "unknown"),
        "data": data or {},
    }
