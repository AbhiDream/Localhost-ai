"""
graph_router.py — FastAPI SSE endpoint backed by LangGraph WorkbenchState machine.

POST /api/agent/graph/stream
  Accepts the same AgentRequest payload as the legacy /api/agent/stream endpoint.
  Runs the request through the LangGraph state machine:
    router_node → [code_execution_node | vision_analysis_node | document_drafting_node]
                → (self-correction loop for code errors, max 2 retries)
                → output_node → SSE stream
  All local model calls, sandbox execution, and RAG retrieval are preserved intact.
"""
import json
import time
from typing import Optional, List, Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import MODELS
from routers.network_monitor import record_call

router = APIRouter()


# ── Request schema (mirrors AgentRequest) ─────────────────────────────────────

class GraphAgentRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []
    model_override: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[List[Any]] = []
    images: Optional[List[str]] = None
    pdf: Optional[str] = None


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _sse_token(text: str) -> str:
    return _sse({"type": "token", "text": text})


def _sse_phase(phase: str, title: str, model_key: str = "reasoning") -> str:
    cfg = MODELS.get(model_key, MODELS["reasoning"])
    return _sse({
        "type": "phase", "phase": phase, "title": title,
        "model": model_key,
        "model_display": cfg["display"],
        "model_tag": cfg["tag"],
        "model_color": cfg["color"],
    })


# ── Streaming endpoint ─────────────────────────────────────────────────────────

@router.post("/stream")
async def graph_agent_stream(req: GraphAgentRequest, request: Request):
    """
    LangGraph-backed agentic SSE endpoint.
    Runs WorkbenchState machine and streams progress + final response.
    """
    record_call("ollama_local", req.message[:80])

    async def event_generator():
        t0 = time.time()

        # Lazy import to avoid import-time errors if langgraph isn't installed yet
        try:
            from workbench_graph import workbench_graph, MAX_RETRIES
        except ImportError as e:
            yield _sse({"type": "error", "message": f"LangGraph not available: {e}"})
            return

        # ── Announce task type ──────────────────────────────────────────────
        yield _sse({
            "type": "meta",
            "task_type": "graph",
            "phases": ["classify", "execute", "output"],
            "model": "reasoning",
            "model_display": MODELS["reasoning"]["display"],
            "model_tag": MODELS["reasoning"]["tag"],
            "model_color": MODELS["reasoning"]["color"],
        })

        # ── Build initial state ─────────────────────────────────────────────
        from langchain_core.messages import HumanMessage, AIMessage
        
        # Build Langchain message history from frontend payload
        langchain_msgs = []
        for msg in (req.history or []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                langchain_msgs.append(HumanMessage(content=content))
            else:
                langchain_msgs.append(AIMessage(content=content))
        
        # Ensure the current message is appended if not already the last in history
        if not langchain_msgs or langchain_msgs[-1].content != req.message:
            langchain_msgs.append(HumanMessage(content=req.message))

        initial_state = {
            "messages": langchain_msgs,
            "user_prompt": req.message,
            "task_type": "",
            "images": req.images,
            "pdf_b64": req.pdf,
            "context": req.context or [],
            "model_override": req.model_override,
            "extracted_text": "",
            "rag_context": "",
            "rag_chunks": [],
            "code": "",
            "sandbox_output": "",
            "sandbox_stderr": "",
            "error_count": 0,
            "final_response": "",
            "artifact": None,
            "phases_completed": [],
        }

        # ── Stream: phase notifications while graph runs ────────────────────
        yield _sse_phase("classify", "Classifying task intent", "reasoning")
        yield _sse_token("*[Graph Node: Router — classifying intent]*\n")

        # Run the graph (async invoke)
        try:
            final_state: dict = await workbench_graph.ainvoke(initial_state)
        except Exception as e:
            yield _sse({"type": "error", "message": f"Graph execution failed: {e}"})
            return

        if await request.is_disconnected():
            return

        # ── Emit per-phase progress from completed phases ───────────────────
        for phase in final_state.get("phases_completed", []):
            if phase == "classify":
                pass  # already emitted above
            elif phase == "extract_pdf":
                yield _sse_phase("extract", "PDF text extraction complete", "ocr")
                yield _sse_token(f"\n> Extracted {len(final_state['extracted_text'])} chars from PDF\n")
            elif phase == "retrieve":
                chunks = final_state.get("rag_chunks", [])
                yield _sse_phase("retrieve", f"Retrieved {len(chunks)} knowledge chunks", "embed")
                for i, c in enumerate(chunks, 1):
                    page = f", page {c['page']}" if c.get("page") else ""
                    yield _sse_token(f"> {i}. `{c['source']}{page}` (dist: {c['distance']})\n")
            elif phase == "code_execution":
                yield _sse_phase("execute", "Sandbox execution succeeded", "code")
                if final_state.get("sandbox_output"):
                    yield _sse_token(f"\n```\n{final_state['sandbox_output']}\n```\n")
            elif phase.startswith("execute-error"):
                attempt = phase.split("-")[-1]
                yield _sse_phase("execute", f"Sandbox error — self-correcting (attempt {attempt})", "code")
                yield _sse_token(f"\n> ⚠ Error detected — asking Qwen Coder to self-correct...\n")
            elif phase == "vision_analysis":
                yield _sse_phase("reason", "Vision analysis complete", "vision")
            elif phase == "document_drafting":
                yield _sse_phase("reason", "Document drafted with Phi-3.5 Mini", "reasoning")
            elif phase.startswith("artifact:"):
                art_type = phase.split(":")[1].upper()
                yield _sse_phase("artifact", f"Generating {art_type} document", "reasoning")

        # ── Stream the final response text ──────────────────────────────────
        yield _sse_phase("reason", "Final response ready", "reasoning")
        yield _sse_token("\n\n")

        final_text = final_state.get("final_response", "")
        # Stream in 80-char chunks so the UI renders progressively
        chunk_size = 80
        for i in range(0, len(final_text), chunk_size):
            if await request.is_disconnected():
                return
            yield _sse_token(final_text[i:i + chunk_size])

        # ── Artifact notification ───────────────────────────────────────────
        if final_state.get("artifact"):
            art = final_state["artifact"]
            yield _sse_token(f"\n\n> ✅ Generated: `{art['file']}`\n")
            yield _sse({
                "type": "artifact",
                "file": art["file"],
                "download_url": art["download_url"],
                "doc_type": art["doc_type"],
            })

        # ── Self-correction exhausted notice ───────────────────────────────
        if (
            final_state.get("task_type") == "code_execution"
            and final_state.get("sandbox_stderr")
            and final_state.get("error_count", 0) >= MAX_RETRIES
        ):
            yield _sse_token(
                f"\n\n> ⚠ Self-correction limit reached after {MAX_RETRIES} attempts. "
                "Review the error trace above.\n"
            )

        # ── DONE ────────────────────────────────────────────────────────────
        latency = round((time.time() - t0) * 1000)
        yield _sse({
            "type": "done",
            "tokens": len(final_text.split()),
            "latency_ms": latency,
            "phases_completed": final_state.get("phases_completed", []),
            "task_type": final_state.get("task_type", ""),
            "external_calls": 0,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
