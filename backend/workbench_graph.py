"""
workbench_graph.py  —  LangGraph StateMachine for LocalHost.AI Workbench

State:  WorkbenchState (TypedDict)
Nodes:  router → execute/vision/document → self_correct (loop) → output
Edges:  conditional routing with self-correction up to MAX_RETRIES

All model calls go to local Ollama. Sandbox runs in a local subprocess.
No cloud dependencies; fully air-gapped compatible.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, AsyncGenerator, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from config import MODELS, OLLAMA_BASE_URL
from routers.network_monitor import record_call


# ─────────────────────────────────────────────────────────────────────────────
# State definition
# ─────────────────────────────────────────────────────────────────────────────

class WorkbenchState(TypedDict):
    """Shared state passed between every node in the graph."""
    user_prompt: str                    # original user message
    task_type: str                      # code_execution | vision_analysis | document_drafting
    # inputs
    images: Optional[List[str]]         # base64-encoded images
    pdf_b64: Optional[str]              # base64-encoded PDF
    context: Optional[List[Any]]        # conversation context tokens
    model_override: Optional[str]       # force a specific model key
    # intermediate artefacts
    extracted_text: str                 # OCR / PDF text
    rag_context: str                    # retrieved knowledge-base context
    rag_chunks: List[dict]              # metadata for retrieved chunks
    code: str                           # latest generated Python code
    sandbox_output: str                 # stdout from sandbox
    sandbox_stderr: str                 # stderr / error trace from sandbox
    error_count: int                    # self-correction attempts so far
    # outputs
    final_response: str                 # formatted answer / narrative
    artifact: Optional[dict]            # {file, download_url, doc_type}
    phases_completed: List[str]         # audit trail


MAX_RETRIES = 2   # maximum auto-fix attempts before giving up


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — thin wrappers around existing infrastructure
# ─────────────────────────────────────────────────────────────────────────────

async def _ollama_generate(prompt: str, model_tag: str, temperature: float = 0.4) -> str:
    """Non-streaming Ollama call used inside graph nodes."""
    import httpx
    record_call("ollama_local", f"graph: {prompt[:60]}")
    payload = {
        "model": model_tag,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 4096, "temperature": temperature, "num_predict": 2048},
    }
    async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=180) as client:
        r = await client.post("/api/generate", json=payload)
        return r.json().get("response", "")


def _extract_code_blocks(text: str) -> list[str]:
    """Pull Python fenced blocks from model output."""
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: router_node  — classify intent
# ─────────────────────────────────────────────────────────────────────────────

async def router_node(state: WorkbenchState) -> WorkbenchState:
    """
    Classify the incoming prompt into one of:
      code_execution | vision_analysis | document_drafting
    Updates state["task_type"] in-place.
    """
    prompt = state["user_prompt"]
    has_image = bool(state.get("images"))
    has_pdf = bool(state.get("pdf_b64"))

    # Vision: always when image is attached
    if has_image:
        state["task_type"] = "vision_analysis"
        return state

    lower = prompt.lower()

    # Heuristic keyword scoring (mirrors config.py classify_task but in graph form)
    code_score = sum(
        1 for kw in [
            "python", "script", "code", "calculate", "formula", "lmtd",
            "algorithm", "function", "compute", "engineering calculation",
        ]
        if kw in lower
    )
    doc_score = sum(
        1 for kw in [
            "report", "approval note", "draft", "sop", "inspection report",
            "docx", "word", "presentation", "slides", "pptx",
        ]
        if kw in lower
    )

    if code_score >= doc_score and code_score > 0:
        state["task_type"] = "code_execution"
    elif doc_score > 0:
        state["task_type"] = "document_drafting"
    else:
        # Fallback to code_execution for anything technical with a PDF, else document_drafting
        state["task_type"] = "document_drafting" if has_pdf else "code_execution"

    state["phases_completed"].append("classify")
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Node 2a: code_execution_node  — Qwen Coder → sandbox
# ─────────────────────────────────────────────────────────────────────────────

async def code_execution_node(state: WorkbenchState) -> WorkbenchState:
    """
    Call local Qwen 2.5 Coder to generate Python, then run it in the sandbox.
    Stores generated code, sandbox stdout/stderr back into state.
    """
    coder_tag = MODELS["code"]["tag"]

    # Build the coding prompt (include error trace on retry)
    if state["error_count"] > 0 and state["sandbox_stderr"]:
        prompt = (
            "You are a Python engineering assistant. The previous code had an error.\n\n"
            f"ERROR TRACE:\n{state['sandbox_stderr']}\n\n"
            f"PREVIOUS CODE:\n```python\n{state['code']}\n```\n\n"
            "Fix the code so it runs without errors. "
            "Return ONLY one complete ```python block, no explanation."
        )
    else:
        execution_note = (
            "This code runs non-interactively in a headless sandbox. "
            "NEVER call input(). Use fixed sample values for any user inputs."
        )
        prompt = (
            "You are a Python engineering assistant. "
            "Return one complete, runnable Python solution in a fenced ```python block. "
            f"{execution_note}\n\n"
            f"User request: {state['user_prompt']}"
        )

    record_call("ollama_local", f"qwen-coder: {state['user_prompt'][:60]}")
    raw = await _ollama_generate(prompt, coder_tag, temperature=0.2)
    state["final_response"] = raw

    blocks = _extract_code_blocks(raw)
    if blocks:
        state["code"] = blocks[0]
    else:
        state["code"] = raw   # treat whole response as code if no fencing

    # Execute in local subprocess sandbox
    from routers.sandbox import run_code_sandboxed
    result = await run_code_sandboxed(state["code"], timeout=30)

    state["sandbox_output"] = result["stdout"]
    state["sandbox_stderr"] = result["stderr"]
    state["phases_completed"].append(
        "execute" if result["status"] == "success" else f"execute-error-{state['error_count']}"
    )
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Node 2b: vision_analysis_node  — LLaVA-Phi3 multimodal
# ─────────────────────────────────────────────────────────────────────────────

async def vision_analysis_node(state: WorkbenchState) -> WorkbenchState:
    """Send image(s) directly to the local vision model (LLaVA-Phi3)."""
    import httpx

    vision_tag = MODELS["vision"]["tag"]
    prompt = (
        "Analyze this image carefully. Describe all visible components, labels, "
        "text, symbols, and spatial relationships.\n\n"
        f"User query: {state['user_prompt']}"
    )

    payload = {
        "model": vision_tag,
        "prompt": prompt,
        "stream": False,
        "images": state.get("images", []),
        "options": {"num_ctx": 4096, "temperature": 0.3},
    }

    record_call("ollama_local", f"vision: {state['user_prompt'][:60]}")
    async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=180) as client:
        r = await client.post("/api/generate", json=payload)
        state["final_response"] = r.json().get("response", "[Vision model returned no output]")

    state["phases_completed"].append("vision_analysis")
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Node 2c: document_drafting_node  — Phi-3.5 with RAG context
# ─────────────────────────────────────────────────────────────────────────────

async def document_drafting_node(state: WorkbenchState) -> WorkbenchState:
    """
    1. Extract text from attached PDF if present.
    2. Retrieve RAG context.
    3. Call Phi-3.5 Mini to draft the document.
    """
    reasoning_tag = MODELS["reasoning"]["tag"]

    # PDF extraction
    if state.get("pdf_b64") and not state["extracted_text"]:
        try:
            from routers.agent import phase_extract_pdf
            state["extracted_text"] = await phase_extract_pdf(state["pdf_b64"])
            state["phases_completed"].append("extract_pdf")
        except Exception as e:
            state["extracted_text"] = f"[PDF extraction failed: {e}]"

    # RAG retrieval
    if not state["rag_context"]:
        try:
            from routers.agent import phase_retrieve
            rag_ctx, rag_chunks = await phase_retrieve(state["user_prompt"])
            state["rag_context"] = rag_ctx
            state["rag_chunks"] = rag_chunks
            state["phases_completed"].append("retrieve")
        except Exception:
            state["rag_context"] = ""
            state["rag_chunks"] = []

    # Build evidence block
    parts = []
    if state["extracted_text"]:
        parts.append(state["extracted_text"])
    if state["rag_context"]:
        parts.append(f"[Knowledge Base]:\n{state['rag_context']}")
    evidence = "\n\n---\n\n".join(parts)

    if evidence:
        prompt = (
            "You are LocalHost.AI preparing an internal industrial document. "
            "Use ONLY the EVIDENCE below. Do not invent measurements or dates. "
            "Include source markers for every factual statement.\n\n"
            f"EVIDENCE:\n{evidence}\n\n"
            f"REQUEST: {state['user_prompt']}\n\n"
            "Write sections: Evidence Summary, Findings, Risk / Data Gaps, Recommended Next Action."
        )
    else:
        prompt = (
            "You are LocalHost.AI, a helpful air-gapped industrial assistant. "
            f"User request: {state['user_prompt']}\n\n"
            "Respond clearly and professionally."
        )

    record_call("ollama_local", f"phi3.5 doc: {state['user_prompt'][:60]}")
    state["final_response"] = await _ollama_generate(prompt, reasoning_tag, temperature=0.3)
    state["phases_completed"].append("document_drafting")
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: output_node  — format & optionally generate artefact
# ─────────────────────────────────────────────────────────────────────────────

async def output_node(state: WorkbenchState) -> WorkbenchState:
    """
    Append sandbox output to final_response and optionally produce a .docx/.py artifact.
    """
    # Append sandbox results for code tasks
    if state["task_type"] == "code_execution" and state["sandbox_output"]:
        state["final_response"] += (
            f"\n\n---\n**Sandbox Output:**\n```\n{state['sandbox_output']}\n```"
        )
    if state["task_type"] == "code_execution" and state["sandbox_stderr"] and state["error_count"] >= MAX_RETRIES:
        state["final_response"] += (
            f"\n\n> ⚠ Self-correction exhausted after {MAX_RETRIES} retries.\n"
            f"```\n{state['sandbox_stderr'][:500]}\n```"
        )

    # Detect if user wants a document artefact
    from routers.agent import detect_artifact_type, phase_artifact, extract_code_blocks

    art_type = detect_artifact_type(state["user_prompt"])
    if art_type:
        try:
            title = "MRPL " + state["user_prompt"][:60].title()
            artifact = await phase_artifact(state["final_response"], title, art_type)
            state["artifact"] = artifact
            state["phases_completed"].append(f"artifact:{art_type}")
        except Exception as e:
            state["artifact"] = None

    state["phases_completed"].append("output")
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Edge logic — conditional routing
# ─────────────────────────────────────────────────────────────────────────────

def route_after_classify(state: WorkbenchState) -> str:
    """Map task_type to execution node name."""
    return {
        "code_execution": "code_execution_node",
        "vision_analysis": "vision_analysis_node",
        "document_drafting": "document_drafting_node",
    }.get(state["task_type"], "document_drafting_node")


def route_after_code_execution(state: WorkbenchState) -> str:
    """
    Self-correction edge:
      - If sandbox error and under retry budget → loop back to code_execution_node
      - Otherwise → output_node
    """
    has_error = bool(state["sandbox_stderr"]) and not state["sandbox_output"]
    if has_error and state["error_count"] < MAX_RETRIES:
        state["error_count"] += 1
        return "code_execution_node"
    return "output_node"


# ─────────────────────────────────────────────────────────────────────────────
# Build the graph
# ─────────────────────────────────────────────────────────────────────────────

def build_workbench_graph():
    """Compile and return the LangGraph StateGraph."""
    g = StateGraph(WorkbenchState)

    # Register nodes
    g.add_node("router_node", router_node)
    g.add_node("code_execution_node", code_execution_node)
    g.add_node("vision_analysis_node", vision_analysis_node)
    g.add_node("document_drafting_node", document_drafting_node)
    g.add_node("output_node", output_node)

    # Entry point
    g.set_entry_point("router_node")

    # router → one of the three execution nodes
    g.add_conditional_edges(
        "router_node",
        route_after_classify,
        {
            "code_execution_node": "code_execution_node",
            "vision_analysis_node": "vision_analysis_node",
            "document_drafting_node": "document_drafting_node",
        },
    )

    # code_execution_node → self-correct loop or output
    g.add_conditional_edges(
        "code_execution_node",
        route_after_code_execution,
        {
            "code_execution_node": "code_execution_node",
            "output_node": "output_node",
        },
    )

    # vision and document go straight to output
    g.add_edge("vision_analysis_node", "output_node")
    g.add_edge("document_drafting_node", "output_node")

    # output → END
    g.add_edge("output_node", END)

    return g.compile()


# Singleton compiled graph — imported by the FastAPI router
workbench_graph = build_workbench_graph()
