"""
workbench_graph.py  —  LangGraph StateMachine for LocalHost.AI Workbench

State:  WorkbenchState (TypedDict) with messages and memory checkpointing.
Nodes:  router → execute/vision/document → self_correct (loop) → output
Edges:  conditional routing with self-correction up to MAX_RETRIES

All model calls go to local Ollama via /api/chat. Sandbox runs in a local subprocess.
"""
from __future__ import annotations

import asyncio
import json
import re
import operator
from typing import Any, AsyncGenerator, List, Optional, TypedDict, Annotated

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, trim_messages
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from config import MODELS, OLLAMA_BASE_URL
from routers.network_monitor import record_call


# ─────────────────────────────────────────────────────────────────────────────
# State definition
# ─────────────────────────────────────────────────────────────────────────────

def add_phases(left: list[str], right: list[str]) -> list[str]:
    if not right: return []
    return left + right

class WorkbenchState(TypedDict):
    """Shared state passed between every node in the graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    
    user_prompt: str                    # original user message
    task_type: str                      # code_execution | vision_analysis | document_drafting
    # inputs
    images: Optional[List[str]]         # base64-encoded images
    pdf_b64: Optional[str]              # base64-encoded PDF
    context: Optional[List[Any]]        # legacy conversation context tokens (optional)
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
    phases_completed: Annotated[List[str], add_phases] # audit trail


MAX_RETRIES = 2   # maximum auto-fix attempts before giving up


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — thin wrappers around existing infrastructure
# ─────────────────────────────────────────────────────────────────────────────

def _trim_context(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Trim conversation history to fit context window while keeping system prompts."""
    return trim_messages(
        messages,
        max_tokens=6,  # 6 messages (turns) roughly aligns with the requirement
        token_counter=len, # simple message count proxy
        strategy="last",
        include_system=True,
        allow_partial=False
    )

async def _ollama_chat(messages: list[BaseMessage], model_tag: str, temperature: float = 0.4, images: Optional[List[str]] = None) -> str:
    """Non-streaming Ollama chat call used inside graph nodes."""
    import httpx
    record_call("ollama_local", f"graph chat: {messages[-1].content[:60]}")
    
    mapping = {"system": "system", "human": "user", "ai": "assistant"}
    ollama_msgs = []
    
    for idx, m in enumerate(messages):
        msg = {"role": mapping.get(m.type, "user"), "content": m.content}
        # Inject images into the last user message if provided
        if images and idx == len(messages) - 1 and msg["role"] == "user":
            msg["images"] = images
        ollama_msgs.append(msg)
        
    payload = {
        "model": model_tag,
        "messages": ollama_msgs,
        "stream": False,
        "options": {"num_ctx": 4096, "temperature": temperature, "num_predict": 2048},
    }
    async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=180) as client:
        r = await client.post("/api/chat", json=payload)
        return r.json().get("message", {}).get("content", "")


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
    # Ensure user_prompt is synced from the latest message
    prompt = state["user_prompt"]
    has_image = bool(state.get("images"))
    has_pdf = bool(state.get("pdf_b64"))

    # Vision: always when image is attached
    if has_image:
        return {"task_type": "vision_analysis", "phases_completed": ["classify"]}

    lower = prompt.lower()

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
        task = "code_execution"
    elif doc_score > 0:
        task = "document_drafting"
    else:
        task = "document_drafting" if has_pdf else "code_execution"

    return {"task_type": task, "phases_completed": ["classify"]}


# ─────────────────────────────────────────────────────────────────────────────
# Node 2a: code_execution_node  — Qwen Coder → sandbox
# ─────────────────────────────────────────────────────────────────────────────

async def code_execution_node(state: WorkbenchState) -> WorkbenchState:
    """
    Call local Qwen 2.5 Coder to generate Python, then run it in the sandbox.
    Stores generated code, sandbox stdout/stderr back into state.
    """
    coder_tag = MODELS["code"]["tag"]

    if state["error_count"] > 0 and state["sandbox_stderr"]:
        sys_msg = SystemMessage(
            content="You are a Python engineering assistant. The previous code had an error. "
            f"ERROR TRACE:\n{state['sandbox_stderr']}\n\n"
            f"PREVIOUS CODE:\n```python\n{state['code']}\n```\n\n"
            "Fix the code so it runs without errors. "
            "Return ONLY one complete ```python block, no explanation."
        )
    else:
        sys_msg = SystemMessage(
            content="You are a Python engineering assistant. "
            "Return one complete, runnable Python solution in a fenced ```python block. "
            "This code runs non-interactively in a headless sandbox. "
            "NEVER call input(). Use fixed sample values for any user inputs."
        )
    
    # Trim conversation history, leaving room for our new SystemMessage
    trimmed_msgs = _trim_context(state["messages"])
    
    # Prepend the task-specific system instruction
    chat_msgs = [sys_msg] + [m for m in trimmed_msgs if not isinstance(m, SystemMessage)]

    raw = await _ollama_chat(chat_msgs, coder_tag, temperature=0.2)
    
    blocks = _extract_code_blocks(raw)
    code = blocks[0] if blocks else raw

    # Execute in local subprocess sandbox
    from routers.sandbox import run_code_sandboxed
    result = await run_code_sandboxed(code, timeout=30)

    phase_marker = "execute" if result["status"] == "success" else f"execute-error-{state['error_count']}"
    
    return {
        "final_response": raw,
        "code": code,
        "sandbox_output": result["stdout"],
        "sandbox_stderr": result["stderr"],
        "phases_completed": [phase_marker]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2b: vision_analysis_node  — LLaVA-Phi3 multimodal
# ─────────────────────────────────────────────────────────────────────────────

async def vision_analysis_node(state: WorkbenchState) -> WorkbenchState:
    """Send image(s) directly to the local vision model (LLaVA-Phi3)."""
    vision_tag = MODELS["vision"]["tag"]
    
    sys_msg = SystemMessage(
        content="Analyze the image carefully. Describe all visible components, labels, "
        "text, symbols, and spatial relationships."
    )
    
    trimmed_msgs = _trim_context(state["messages"])
    chat_msgs = [sys_msg] + [m for m in trimmed_msgs if not isinstance(m, SystemMessage)]
    
    raw = await _ollama_chat(chat_msgs, vision_tag, temperature=0.3, images=state.get("images"))
    
    return {
        "final_response": raw or "[Vision model returned no output]",
        "phases_completed": ["vision_analysis"]
    }


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
    extracted_text = state["extracted_text"]
    rag_context = state["rag_context"]
    rag_chunks = state["rag_chunks"]
    new_phases = []

    # PDF extraction
    if state.get("pdf_b64") and not extracted_text:
        try:
            from routers.agent import phase_extract_pdf
            extracted_text = await phase_extract_pdf(state["pdf_b64"])
            new_phases.append("extract_pdf")
        except Exception as e:
            extracted_text = f"[PDF extraction failed: {e}]"

    # RAG retrieval
    if not rag_context:
        try:
            from routers.agent import phase_retrieve
            rag_context, rag_chunks = await phase_retrieve(state["user_prompt"])
            new_phases.append("retrieve")
        except Exception:
            rag_context = ""
            rag_chunks = []

    parts = []
    if extracted_text:
        parts.append(extracted_text)
    if rag_context:
        parts.append(f"[Knowledge Base]:\n{rag_context}")
    evidence = "\n\n---\n\n".join(parts)

    if evidence:
        sys_msg = SystemMessage(
            content="You are LocalHost.AI preparing an internal industrial document. "
            "Use ONLY the EVIDENCE below. Do not invent measurements or dates. "
            "Include source markers for every factual statement.\n\n"
            f"EVIDENCE:\n{evidence}\n\n"
            "Write sections: Evidence Summary, Findings, Risk / Data Gaps, Recommended Next Action."
        )
    else:
        sys_msg = SystemMessage(
            content="You are LocalHost.AI, a helpful air-gapped industrial assistant. "
            "Respond clearly and professionally."
        )

    trimmed_msgs = _trim_context(state["messages"])
    chat_msgs = [sys_msg] + [m for m in trimmed_msgs if not isinstance(m, SystemMessage)]

    raw = await _ollama_chat(chat_msgs, reasoning_tag, temperature=0.3)
    new_phases.append("document_drafting")
    
    return {
        "final_response": raw,
        "extracted_text": extracted_text,
        "rag_context": rag_context,
        "rag_chunks": rag_chunks,
        "phases_completed": new_phases
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: output_node  — format & optionally generate artefact
# ─────────────────────────────────────────────────────────────────────────────

async def output_node(state: WorkbenchState) -> WorkbenchState:
    """
    Append sandbox output to final_response and optionally produce a .docx/.py artifact.
    Append the final_response to the message history.
    """
    final_resp = state["final_response"]
    
    # Append sandbox results for code tasks
    if state["task_type"] == "code_execution" and state["sandbox_output"]:
        final_resp += (
            f"\n\n---\n**Sandbox Output:**\n```\n{state['sandbox_output']}\n```"
        )
    if state["task_type"] == "code_execution" and state["sandbox_stderr"] and state["error_count"] >= MAX_RETRIES:
        final_resp += (
            f"\n\n> ⚠ Self-correction exhausted after {MAX_RETRIES} retries.\n"
            f"```\n{state['sandbox_stderr'][:500]}\n```"
        )

    new_phases = ["output"]
    artifact = None
    
    from routers.agent import detect_artifact_type, phase_artifact
    art_type = detect_artifact_type(state["user_prompt"])
    
    if art_type:
        try:
            title = "MRPL " + state["user_prompt"][:60].title()
            artifact = await phase_artifact(final_resp, title, art_type)
            new_phases.append(f"artifact:{art_type}")
        except Exception:
            artifact = None

    # Save the final AI response to message history
    ai_msg = AIMessage(content=final_resp)
            
    return {
        "final_response": final_resp,
        "artifact": artifact,
        "phases_completed": new_phases,
        "messages": [ai_msg]
    }


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
        return "code_execution_node"
    return "output_node"


def increment_error_count(state: WorkbenchState) -> WorkbenchState:
    """Utility to increment error count cleanly during looping."""
    return {"error_count": state["error_count"] + 1}


# ─────────────────────────────────────────────────────────────────────────────
# Build the graph
# ─────────────────────────────────────────────────────────────────────────────

def build_workbench_graph():
    """Compile and return the LangGraph StateGraph with MemorySaver."""
    g = StateGraph(WorkbenchState)

    # Register nodes
    g.add_node("router_node", router_node)
    g.add_node("code_execution_node", code_execution_node)
    g.add_node("increment_error", increment_error_count)
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
            "code_execution_node": "increment_error",
            "output_node": "output_node",
        },
    )
    g.add_edge("increment_error", "code_execution_node")

    # vision and document go straight to output
    g.add_edge("vision_analysis_node", "output_node")
    g.add_edge("document_drafting_node", "output_node")

    # output → END
    g.add_edge("output_node", END)

    # Memory Checkpointer
    memory = MemorySaver()
    return g.compile(checkpointer=memory)


# Singleton compiled graph — imported by the FastAPI router
workbench_graph = build_workbench_graph()
