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
    last_code: Optional[str]            # stored code for reference
    conversation_summary: Optional[str] # sliding summary of older turns
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
    """Non-streaming Ollama chat call with retry logic and OOM-safe limits."""
    import httpx
    record_call("ollama_local", f"graph chat: {messages[-1].content[:60]}")
    
    mapping = {"system": "system", "human": "user", "ai": "assistant"}
    ollama_msgs = []
    
    for idx, m in enumerate(messages):
        msg = {"role": mapping.get(m.type, "user"), "content": m.content}
        if images and idx == len(messages) - 1 and msg["role"] == "user":
            msg["images"] = images
        ollama_msgs.append(msg)
        
    payload = {
        "model": model_tag,
        "messages": ollama_msgs,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 1024,   # hard limit — prevents OOM on long chains
            "num_ctx":     2048,   # trim context window — avoids memory overload
        },
    }

    timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=timeout) as client:
                r = await client.post("/api/chat", json=payload)
                r.raise_for_status()
                return r.json().get("message", {}).get("content", "")
        except httpx.ReadTimeout:
            if attempt == 0:
                continue   # one free retry
            return "[Response timed out. Try a simpler query or break the task into smaller steps.]"
        except Exception as exc:
            return f"[Model error: {exc}]"
    return "[Model unavailable]"


def _extract_code_blocks(text: str) -> list[tuple[str, str]]:
    """Extract ALL fenced code blocks with their language tag.
    Returns list of (code_body, language) tuples.
    Language is lowercase, e.g. 'python', 'c', 'cpp', 'java', 'javascript', ''.
    """
    blocks = re.findall(r"```(\w*)\s*\n(.*?)```", text, re.DOTALL)
    return [(body.strip(), lang.lower()) for lang, body in blocks if body.strip()]


def _detect_language(code: str, raw: str) -> str:
    """Detect code language from explicit fence tag first, then content heuristics."""
    # 1. Trust the explicit fence tag in the raw response
    tag_match = re.search(r"```(c\+\+|cpp|c|javascript|js|java|python)\b", raw, re.IGNORECASE)
    if tag_match:
        tag = tag_match.group(1).lower()
        if tag in ("c++", "cpp"):       return "cpp"
        if tag == "c":                  return "c"
        if tag in ("js", "javascript"): return "javascript"
        if tag == "java":               return "java"
        if tag == "python":             return "python"

    # 2. Content heuristics as fallback
    if "#include" in code or "int main(" in code or "printf(" in code:
        return "c"
    if "public class" in code or "System.out.println" in code:
        return "java"
    if "def " in code or "import " in code or "print(" in code or "__name__" in code:
        return "python"
    if "console.log(" in code and "def " not in code:
        return "javascript"
    return "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: router_node  — classify intent
# ─────────────────────────────────────────────────────────────────────────────

async def router_node(state: WorkbenchState) -> WorkbenchState:
    """
    Classify the incoming prompt using Phi-3.5 and recent conversation history.
    Summarize older messages if history exceeds 20 messages.
    """
    messages = state["messages"]
    summary = state.get("conversation_summary", "")
    msgs_to_remove = []

    # 1. Summarize if history is too long (Part 5)
    if len(messages) > 20:
        to_summarize = messages[:-6]
        prompt = "Summarize the following conversation history concisely:\n"
        for m in to_summarize:
            prompt += f"{m.type}: {m.content}\n"
        if summary:
            prompt = f"Previous summary: {summary}\n\n" + prompt
            
        summary_payload = {
            "model": MODELS["reasoning"]["tag"],
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.2}
        }
        import httpx
        try:
            async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=60) as client:
                r = await client.post("/api/chat", json=summary_payload)
                summary = r.json().get("message", {}).get("content", summary)
        except Exception as e:
            pass
            
        from langchain_core.messages import RemoveMessage
        msgs_to_remove = [RemoveMessage(id=m.id) for m in to_summarize if m.id]

    # Vision check short-circuit
    has_image = bool(state.get("images"))
    if has_image:
        return {"task_type": "vision_analysis", "phases_completed": ["classify"], "conversation_summary": summary, "messages": msgs_to_remove}

    # 2. LLM Routing using recent context (Part 2)
    recent_context = ""
    for m in messages[-6:]:
        recent_context += f"{m.type}: {m.content}\n"
        
    last_code = state.get("last_code", "")
    
    router_prompt = f"""You are a routing assistant. Classify the user's latest request into exactly one category:
- "code_execution": Writing, modifying, fixing code. Also applies to "same code", "in C", "add error handling".
- "vision_analysis": Analyzing images or pictures.
- "document_drafting": General questions, report writing, summaries, or anything else.

Recent conversation context:
{recent_context}

Last generated code:
{last_code}

Respond with ONLY the category name."""
    
    router_payload = {
        "model": MODELS["reasoning"]["tag"],
        "messages": [{"role": "user", "content": router_prompt}],
        "stream": False,
        "options": {"temperature": 0.1}
    }
    
    import httpx
    try:
        async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=60) as client:
            r = await client.post("/api/chat", json=router_payload)
            resp = r.json().get("message", {}).get("content", "").strip().lower()
    except Exception:
        resp = "document_drafting"
        
    task_type = "document_drafting"
    if "code_execution" in resp:
        task_type = "code_execution"
    elif "vision_analysis" in resp or bool(state.get("images")):
        task_type = "vision_analysis"

    return {
        "task_type": task_type, 
        "phases_completed": ["classify"],
        "conversation_summary": summary,
        "messages": msgs_to_remove
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2a: code_execution_node  — Qwen Coder → sandbox
# ─────────────────────────────────────────────────────────────────────────────

async def code_execution_node(state: WorkbenchState) -> WorkbenchState:
    """
    Call local Qwen 2.5 Coder to generate Python, then run it in the sandbox.
    Stores generated code, sandbox stdout/stderr back into state.
    """
    coder_tag = MODELS["code"]["tag"]
    summary = state.get("conversation_summary", "")
    summary_text = f"CONVERSATION SUMMARY: {summary}\n\n" if summary else ""

    if state["error_count"] > 0 and state["sandbox_stderr"]:
        sys_msg = SystemMessage(
            content=f"{summary_text}You are a Python engineering assistant. The previous code had an error. "
            f"ERROR TRACE:\n{state['sandbox_stderr']}\n\n"
            f"PREVIOUS CODE:\n```python\n{state['code']}\n```\n\n"
            "Fix the code so it runs without errors. "
            "Return ONLY one complete ```python block, no explanation."
        )
    else:
        sys_msg = SystemMessage(
            content=f"{summary_text}You are a Python engineering assistant. "
            "Return one complete, runnable Python solution in a fenced ```python block. "
            "This code runs non-interactively in a headless sandbox. "
            "NEVER call input(). Use fixed sample values for any user inputs."
        )
    
    # Trim conversation history, leaving room for our new SystemMessage
    trimmed_msgs = _trim_context(state["messages"])
    
    # Prepend the task-specific system instruction
    chat_msgs = [sys_msg] + [m for m in trimmed_msgs if not isinstance(m, SystemMessage)]

    raw = await _ollama_chat(chat_msgs, coder_tag, temperature=0.2)
    
    blocks = _extract_code_blocks(raw)              # [(code_body, lang), ...]
    code, lang = blocks[0] if blocks else (raw, "")

    # ── Language detection (explicit tag wins over heuristics) ─────────────
    detected = _detect_language(code, raw)

    sandbox_instructions = {
        "c":          "C code generated. Compile locally with:\n  gcc script.c -o output && ./output",
        "cpp":        "C++ code generated. Compile locally with:\n  g++ script.cpp -o output && ./output",
        "java":       "Java code generated. Compile with:\n  javac Main.java && java Main",
        "javascript": "JavaScript code generated. Run with:\n  node script.js",
        "unknown":    "Code generated. Manual execution required for this language.",
    }

    if detected in sandbox_instructions:
        return {
            "final_response": raw,
            "code": code,
            "last_code": code,
            "sandbox_output": sandbox_instructions[detected],
            "sandbox_stderr": "",
            "phases_completed": ["code_execution"],
        }

    # ── Python-only: execute in local subprocess sandbox ───────────────────
    from routers.sandbox import run_code_sandboxed
    result = await run_code_sandboxed(code, timeout=30)

    phase_marker = "code_execution" if result["status"] == "success" else f"execute-error-{state['error_count']}"
    
    return {
        "final_response": raw,
        "code": code,
        "last_code": code,
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
    summary = state.get("conversation_summary", "")
    summary_text = f"CONVERSATION SUMMARY: {summary}\n\n" if summary else ""
    
    sys_msg = SystemMessage(
        content=f"{summary_text}Analyze the image carefully. Describe all visible components, labels, "
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
    summary = state.get("conversation_summary", "")
    summary_text = f"CONVERSATION SUMMARY: {summary}\n\n" if summary else ""
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
            content=f"{summary_text}You are LocalHost.AI preparing an internal industrial document. "
            "Use ONLY the EVIDENCE below. Do not invent measurements or dates. "
            "Include source markers for every factual statement.\n\n"
            f"EVIDENCE:\n{evidence}\n\n"
            "Write sections: Evidence Summary, Findings, Risk / Data Gaps, Recommended Next Action."
        )
    else:
        sys_msg = SystemMessage(
            content=f"{summary_text}You are LocalHost.AI, a helpful air-gapped industrial assistant. "
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

    # Return graph without checkpointer (history managed by frontend)
    return g.compile()


# Singleton compiled graph — imported by the FastAPI router
workbench_graph = build_workbench_graph()
