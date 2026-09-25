"""
Code sandbox — executes generated Python scripts in an isolated subprocess.
Timeout-limited, output captured. No network access.
"""
import asyncio
import os
import sys
import uuid
import re
import subprocess
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from routers.network_monitor import record_call

router = APIRouter()
OUTPUT_DIR = Path("outputs").resolve()  # absolute path
OUTPUT_DIR.mkdir(exist_ok=True)


class ExecuteRequest(BaseModel):
    code: str
    timeout: int = 30


class ExecuteResponse(BaseModel):
    status: str
    stdout: str
    stderr: str
    return_code: int
    script_file: str
    external_calls: int = 0


async def run_code_sandboxed(code: str, timeout: int = 30) -> dict:
    """Run Python code in a subprocess. Reusable by agent pipeline."""
    record_call("sandbox_local", f"execute: {code[:60]}")

    # A model may still ignore the prompt. Reject interactive programs before
    # launching them so the UI gives a useful deterministic error instead of a
    # confusing EOF failure or timeout.
    if re.search(r"(?<![\w.])input\s*\(", code):
        return {
            "status": "error",
            "stdout": "",
            "stderr": "Interactive input() is not supported in the headless sandbox. Use fixed sample values or function parameters.",
            "return_code": -1,
            "script_file": "",
            "external_calls": 0,
        }

    script_id = uuid.uuid4().hex[:8]
    script_name = f"sandbox_{script_id}.py"
    script_path = OUTPUT_DIR / script_name
    script_path.write_text(code, encoding="utf-8")

    # The development server can be launched by a global uvicorn executable,
    # making sys.executable a Python without project dependencies (e.g. numpy).
    # Prefer this backend's virtual environment whenever it exists.
    venv_python = Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe"
    python_exe = str(venv_python) if venv_python.is_file() else sys.executable
    abs_script = str(script_path.resolve())

    try:
        # asyncio's Windows subprocess transport can return -1 without stderr
        # under uvicorn's reload worker, even for `print(2+2)`. Run the blocking
        # process in a worker thread instead; subprocess.run is reliable on
        # Windows and still leaves FastAPI's event loop free.
        # -E prevents a terminal-level PYTHONHOME/PYTHONPATH from corrupting
        # the virtual environment's startup ("Failed to import the site
        # module"), while still allowing packages installed in .venv.
        clean_env = os.environ.copy()
        for variable in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONUSERBASE"):
            clean_env.pop(variable, None)

        completed = await asyncio.to_thread(
            subprocess.run,
            [python_exe, "-E", abs_script],
            cwd=str(OUTPUT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=clean_env,
        )
        return {
            "status": "success" if completed.returncode == 0 else "error",
            "stdout": completed.stdout[-5000:],
            "stderr": completed.stderr[-2000:],
            "return_code": completed.returncode,
            "script_file": script_name,
            "external_calls": 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s.",
            "return_code": -1,
            "script_file": script_name,
            "external_calls": 0,
        }
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "return_code": -1,
            "script_file": script_name,
            "external_calls": 0,
        }


@router.post("/execute", response_model=ExecuteResponse)
async def execute_code(req: ExecuteRequest):
    """Run Python code in a sandboxed subprocess with timeout."""
    return await run_code_sandboxed(req.code, req.timeout)
