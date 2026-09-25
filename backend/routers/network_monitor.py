"""
Network monitor — tracks all call attempts.
In air-gapped mode all calls should be to localhost only.
External call counter is always 0 if Ollama is the only backend.
"""
import time
from collections import deque
from threading import Lock

from fastapi import APIRouter

router = APIRouter()

_lock = Lock()
_log: deque = deque(maxlen=200)
_external_count = 0
_internal_count = 0


def record_call(destination: str, preview: str = ""):
    """Called by every router that makes an inference or DB request."""
    global _external_count, _internal_count
    with _lock:
        is_external = not (
            destination.startswith("ollama_local")
            or destination.startswith("chromadb")
            or destination.startswith("localhost")
            or destination.startswith("sandbox_local")
            or destination.startswith("filesystem_local")
        )
        entry = {
            "ts": time.time(),
            "destination": destination,
            "preview": preview[:60],
            "external": is_external,
        }
        _log.append(entry)
        if is_external:
            _external_count += 1
        else:
            _internal_count += 1


@router.get("/stats")
async def network_stats():
    with _lock:
        recent = list(_log)[-20:]
    return {
        "external_calls": _external_count,
        "internal_calls": _internal_count,
        "recent_log": recent,
        "sovereignty": "VERIFIED" if _external_count == 0 else "COMPROMISED",
    }


@router.post("/reset")
async def reset_stats():
    global _external_count, _internal_count
    with _lock:
        _log.clear()
        _external_count = 0
        _internal_count = 0
    return {"reset": True}
