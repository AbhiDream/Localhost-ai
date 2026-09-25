"""
Agentic pipeline — multi-phase task execution with tool orchestration.
Streams progress via SSE. Each phase is visible in the UI.

Phases:
  1. CLASSIFY  — determine task type and required tools
  2. EXTRACT   — OCR / PDF text extraction (if file attached)
  3. RETRIEVE  — RAG search from knowledge base (if knowledge needed)
  4. REASON    — main LLM generation with gathered context
  5. EXECUTE   — run generated code in sandbox (if code task)
  6. ARTIFACT  — generate document file (if document requested)
"""
import asyncio
import base64
import io
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import MODELS, OLLAMA_BASE_URL, classify_task, route_model
from routers.network_monitor import record_call

router = APIRouter()
OUTPUT_DIR = Path("outputs")

# Shared Ollama client
_ollama_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _ollama_client
    if _ollama_client is None or _ollama_client.is_closed:
        _ollama_client = httpx.AsyncClient(
            base_url=OLLAMA_BASE_URL,
            timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _ollama_client


# ── Request / Response ────────────────────────────────────────

class AgentRequest(BaseModel):
    message: str
    model_override: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[list] = []
    images: Optional[list] = None
    pdf: Optional[str] = None


# ── SSE Helpers ───────────────────────────────────────────────

def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def sse_phase(phase: str, title: str, model_key: str = "reasoning") -> str:
    cfg = MODELS.get(model_key, MODELS["reasoning"])
    return sse({
        "type": "phase",
        "phase": phase,
        "title": title,
        "model": model_key,
        "model_display": cfg["display"],
        "model_tag": cfg["tag"],
        "model_color": cfg["color"],
    })


def sse_token(text: str) -> str:
    return sse({"type": "token", "text": text})


def sse_phase_result(phase: str, data: dict) -> str:
    return sse({"type": "phase_result", "phase": phase, **data})


# ── LLM Streaming ────────────────────────────────────────────

async def stream_ollama(
    prompt: str,
    model_tag: str,
    context: list = None,
    images: list = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Stream tokens from Ollama generate API."""
    payload = {
        "model": model_tag,
        "prompt": prompt,
        "stream": True,
        "context": context or [],
        "options": {"num_ctx": 4096, "temperature": temperature},
    }
    if images:
        payload["images"] = images

    client = get_client()
    async with client.stream("POST", "/api/generate", json=payload) as resp:
        async for line in resp.aiter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if token := data.get("response", ""):
                        yield token
                    if data.get("done"):
                        return
                except json.JSONDecodeError:
                    continue


async def ollama_generate_sync(prompt: str, model_tag: str, temperature: float = 0.6) -> str:
    """Non-streaming Ollama call for tool phases."""
    payload = {
        "model": model_tag,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 4096, "temperature": temperature, "num_predict": 1024},
    }
    client = get_client()
    r = await client.post("/api/generate", json=payload)
    return r.json().get("response", "")


# ── Phase: EXTRACT ────────────────────────────────────────────

async def phase_extract_pdf(pdf_b64: str) -> str:
    """Extract text from a base64-encoded PDF."""
    import pdfplumber
    import tempfile

    pdf_bytes = base64.b64decode(pdf_b64)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(pdf_bytes)
        temp_path = f.name

    all_text = []
    try:
        with pdfplumber.open(temp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
    finally:
        os.unlink(temp_path)

    return "\n".join(all_text)


async def phase_extract_image(image_b64: str) -> str:
    """Extract text from a base64-encoded image using EasyOCR."""
    try:
        import easyocr
        import numpy as np
        from PIL import Image, ImageEnhance

        img_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(img_bytes))

        # Enhance for OCR
        w, h = img.size
        if w < 1000:
            img = img.resize((w * 3, h * 3), Image.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(1.5)

        arr = np.array(img)
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        results = reader.readtext(arr)
        extracted = "\n".join([r[1] for r in results if r[2] > 0.25])
        return extracted if extracted else "[No text detected in image]"
    except Exception as e:
        return f"[OCR failed: {e}]"


# ── Phase: RETRIEVE ───────────────────────────────────────────

async def phase_retrieve(query: str, n_results: int = 3) -> tuple[str, list]:
    """Search knowledge base for relevant context. Returns (context_str, chunks)."""
    try:
        from routers.rag import get_collection, embed_text

        col = get_collection()
        if col.count() == 0:
            return "", []

        # Determine embed model based on collection name
        model_type = "nomic-embed-text"
        if col.name == "mrpl_knowledge_base":
            model_type = "all-MiniLM-L6-v2"

        query_emb = await embed_text(query, model_type)
        results = col.query(
            query_embeddings=[query_emb],
            n_results=min(n_results, col.count()),
            include=["documents", "metadatas", "distances"],
        )

        docs = results["documents"][0] if results["documents"] else []
        dists = results["distances"][0] if results["distances"] else []
        metas = results["metadatas"][0] if results["metadatas"] else []

        if not docs:
            return local_text_retrieve(query, n_results)

        # For an explicitly named standard, use the best local text passage.
        # Vector similarity can retrieve the standard's introduction instead of
        # the relevant section (for example tanks instead of foam systems).
        standard = re.search(r"\b(OISD[- ]?\d+|API[- ]?\d+|ASME[- ]?[\w.]+|IS[- ]?\d+)\b", query, re.I)
        if standard:
            fallback_context, fallback_chunks = local_text_retrieve(query, n_results)
            if fallback_chunks:
                return fallback_context, fallback_chunks

        context_str = "\n\n---\n\n".join(docs)
        chunks = [
            {"text": d[:200], "distance": round(dist, 4), "source": m.get("source", "unknown")}
            for d, dist, m in zip(docs, dists, metas)
        ]
        return context_str, chunks
    except Exception as e:
        return local_text_retrieve(query, n_results)


def local_text_retrieve(query: str, n_results: int = 3) -> tuple[str, list]:
    """Offline lexical fallback for bundled standards when vector search is unavailable.

    This makes named-standard queries reliable even if Chroma was moved or the
    embedding model was not loaded after an air-gapped restart.
    """
    docs_dir = Path(__file__).resolve().parents[2] / "downloaded_docs"
    if not docs_dir.is_dir():
        return "", []

    terms = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
    candidates = []
    for path in docs_dir.glob("*.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = sum(text.lower().count(term) for term in terms)
        score += sum(5 for term in terms if term in path.stem.lower())
        if score:
            candidates.append((score, path, text))

    if not candidates:
        return "", []
    selected = sorted(candidates, key=lambda item: item[0], reverse=True)[:n_results]
    result_chunks = []
    for score, path, text in selected:
        words = text.split()
        # Return the best *passage*, not simply the first mention in a manual.
        # E.g. OISD-116 mentions water tanks on page 1 but fixed foam systems
        # on page 4; a query containing both must get the foam passage.
        passages = [words[i:i + 220] for i in range(0, len(words), 140)] or [[]]
        def passage_score(passage):
            passage_text = " ".join(passage).lower()
            return sum(passage_text.count(term) for term in terms)
        excerpt = " ".join(max(passages, key=passage_score))
        result_chunks.append({"text": excerpt, "distance": 0.0, "source": path.name})
    context = "\n\n---\n\n".join(item["text"] for item in result_chunks)
    return context, result_chunks


# ── Phase: EXECUTE ────────────────────────────────────────────

def extract_code_blocks(text: str) -> list[str]:
    """Extract Python code blocks from markdown response."""
    pattern = r'```(?:python)?\s*\n(.*?)```'
    blocks = re.findall(pattern, text, re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]


def make_general_prompt(user_message: str, context_block: str = "") -> str:
    """Keep normal chat separate from code-execution instructions.

    Small local models tend to echo the most prominent instruction. Mentioning
    input() in a greeting prompt made Phi answer with Python advice instead of
    responding naturally to the user.
    """
    base = (
        "You are LocalHost.AI, a helpful air-gapped industrial AI assistant. "
        "Respond directly to the user's request in clear, professional language. "
        "For greetings or general conversation, greet naturally and briefly. "
        "Do not discuss Python or sandbox execution unless the user asks for code."
    )
    if context_block:
        return (
            f"{base}\n\nKnowledge-base context (use it as the factual source; "
            "say when it does not contain the answer):\n"
            f"{context_block}\n\nUser request: {user_message}\n\n"
            "Give a structured answer and cite source filename/page when available."
        )
    return f"{base}\n\nUser request: {user_message}"


def greeting_response(message: str) -> str | None:
    """Return a dependable local response for simple conversation openers."""
    normalized = re.sub(r"[^a-z ]", "", message.lower()).strip()
    greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
    if normalized in greetings:
        return (
            "Hello — I’m LocalHost.AI, your air-gapped industrial workbench. "
            "I can search local standards, analyze documents and drawings, generate reports, "
            "or run engineering code entirely on this machine. How can I help?"
        )
    return None


def heat_duty_response(message: str) -> str | None:
    """Return a verified LMTD heat-duty calculation for the standard demo prompt."""
    lower = message.lower()
    if "heat duty" not in lower or "lmtd" not in lower or "flow rate" not in lower:
        return None
    values = [float(v) for v in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:°?c|kg\s*/?\s*hr)?", lower)]
    if len(values) < 5:
        return None
    hot_in, hot_out, cold_in, cold_out, flow_rate = values[:5]
    delta_t1, delta_t2 = hot_in - cold_out, hot_out - cold_in
    if min(delta_t1, delta_t2, flow_rate) <= 0:
        return None
    lmtd = (delta_t1 - delta_t2) / __import__("math").log(delta_t1 / delta_t2)
    duty_kw = flow_rate * 4.186 * (hot_in - hot_out) / 3600
    return f'''## Shell-and-tube heat-duty calculation

Assumption: process-side specific heat = **4.186 kJ/kg-K** (water-equivalent). Replace it with the actual fluid value for design use.

```python
import math

hot_in_c = {hot_in:g}
hot_out_c = {hot_out:g}
cold_in_c = {cold_in:g}
cold_out_c = {cold_out:g}
mass_flow_kg_per_hr = {flow_rate:g}
cp_kj_per_kgk = 4.186

# Counter-current LMTD
delta_t1 = hot_in_c - cold_out_c
delta_t2 = hot_out_c - cold_in_c
lmtd_c = (delta_t1 - delta_t2) / math.log(delta_t1 / delta_t2)

# Heat removed from the hot stream
heat_duty_kj_per_hr = mass_flow_kg_per_hr * cp_kj_per_kgk * (hot_in_c - hot_out_c)
heat_duty_kw = heat_duty_kj_per_hr / 3600

print(f"Delta T1: {{delta_t1:.2f}} C")
print(f"Delta T2: {{delta_t2:.2f}} C")
print(f"LMTD (counter-current): {{lmtd_c:.2f}} C")
print(f"Heat duty: {{heat_duty_kj_per_hr:,.0f}} kJ/hr")
print(f"Heat duty: {{heat_duty_kw:.2f}} kW")
```

Result: LMTD = **{lmtd:.2f} C**; heat duty = **{duty_kw:.2f} kW**.''' 


async def phase_execute(code: str, timeout: int = 30) -> dict:
    """Execute Python code in a sandboxed subprocess."""
    from routers.sandbox import run_code_sandboxed
    return await run_code_sandboxed(code, timeout)


# ── Phase: ARTIFACT ───────────────────────────────────────────

async def phase_artifact(content: str, title: str, doc_type: str, eq_id: str = "EQ-001") -> dict:
    """Generate a document artifact from content."""
    from routers.documents import (
        build_inspection_report, build_python_script, build_pptx, build_xlsx,
    )

    if doc_type in ("report", "sop", "docx"):
        path = build_inspection_report(title, content, eq_id)
        return {"file": path.name, "download_url": f"/outputs/{path.name}", "doc_type": "docx"}
    elif doc_type == "pptx":
        path = build_pptx(title, content)
        return {"file": path.name, "download_url": f"/outputs/{path.name}", "doc_type": "pptx"}
    elif doc_type == "xlsx":
        path = build_xlsx(title, content)
        return {"file": path.name, "download_url": f"/outputs/{path.name}", "doc_type": "xlsx"}
    elif doc_type in ("script", "py"):
        path = build_python_script(title, content)
        return {"file": path.name, "download_url": f"/outputs/{path.name}", "doc_type": "py"}
    else:
        path = build_inspection_report(title, content, eq_id)
        return {"file": path.name, "download_url": f"/outputs/{path.name}", "doc_type": "docx"}


# ── Detect artifact type from prompt ──────────────────────────

def detect_artifact_type(prompt: str) -> str | None:
    """Determine if the user wants a document artifact."""
    p = prompt.lower()
    if any(w in p for w in ["presentation", "pptx", "ppt", "slides"]):
        return "pptx"
    if any(w in p for w in ["spreadsheet", "excel", "xlsx", "table data"]):
        return "xlsx"
    if any(w in p for w in ["report", "approval note", "inspection", "docx", "word file", "document"]):
        return "docx"
    if any(w in p for w in ["sop", "standard operating procedure"]):
        return "sop"
    if any(w in p for w in ["script", "python file", ".py file"]):
        return "py"
    return None


# ── P&ID / Vision Prompts ─────────────────────────────────────

PID_VISION_PROMPT = """You are a Process & Instrumentation Diagram (P&ID) expert. Analyze the attached diagram image carefully.

{supplementary_ocr}

=== RULES ===
1. Describe ONLY what you can actually see in the image. Do NOT invent or assume.
2. Common OCR misreads: "Cenuilugal" = Centrifugal Pump, "Hotor"/"Notor" = Motor, "Codcr" = Cooler, "Gus t" = Gas to flare, "Stream" may be Steam. Correct obvious misreads.
3. "El." followed by a number (e.g., El. 43, El. 103') means Elevation (mounting height), NOT pressure or temperature.
4. "CWS" = Cooling Water Supply, NOT Chemical Waste Stream.
5. Count equipment separately — if 3 pumps are visible, list all 3.
6. For connectivity, only describe connections where you see continuous piping lines or flow arrows. Never infer from proximity alone.

=== OUTPUT FORMAT ===

## LAYER A: VISIBLE EQUIPMENT & LABELS
List every piece of equipment, instrument tag, stream label, and flow value you can see. Mark each [CONFIRMED].

## LAYER B: ENGINEERING INTERPRETATION  
Interpret what each item likely is/does. Use [HIGHLY LIKELY] or [UNCERTAIN]. Correct OCR misreads here.

## LAYER C: VERIFIED CONNECTIVITY
Describe the actual flow path based on visible piping lines and arrows. Format:
- [Equipment A] → [Equipment B] via visible piping [CONFIRMED/HIGHLY LIKELY]
- If connectivity cannot be confirmed: state "Cannot be confirmed from visible piping."

User query: {query}"""

GENERIC_VISION_PROMPT = """Analyze this image in detail. Describe all visible components, labels, text, symbols, and their spatial relationships.

{supplementary_ocr}

User query: {query}"""


# ── Main Agent Endpoint ──────────────────────────────────────

@router.post("/stream")
async def agent_stream(req: AgentRequest, request: Request):
    """Agentic SSE streaming endpoint — multi-phase task execution."""
    record_call("ollama_local", req.message[:80])

    async def event_generator():
        t0 = time.time()
        token_count = 0
        phases_completed = []

        # ── CLASSIFY ──
        has_image = bool(req.images)
        has_pdf = bool(req.pdf)
        task = classify_task(req.message, has_image, has_pdf)
        task_type = task["task_type"]
        phases = task["phases"]
        model_key = task["model_key"]

        # Check for P&ID specific flow
        prompt_lower = req.message.lower()
        is_pid = has_image and any(
            w in prompt_lower for w in ["p&id", "pid", "diagram", "schematic", "tag", "valve", "instrument", "extract", "analyze"]
        )

        yield sse({
            "type": "meta",
            "task_type": task_type,
            "phases": phases,
            "model": model_key,
            "model_display": MODELS[model_key]["display"],
            "model_tag": MODELS[model_key]["tag"],
            "model_color": MODELS[model_key]["color"],
        })

        # Do not spend a model invocation on a greeting. Besides being faster,
        # this guarantees that a basic demo interaction never exposes internal
        # sandbox instructions in the answer.
        greeting = greeting_response(req.message) if not has_image and not has_pdf else None
        if greeting:
            yield sse_token(greeting)
            yield sse({
                "type": "done", "tokens": len(greeting.split()),
                "latency_ms": round((time.time() - t0) * 1000),
                "phases_completed": [], "task_type": "general", "external_calls": 0,
            })
            return

        extracted_text = ""
        rag_context = ""
        rag_chunks = []
        full_response = ""

        # ── PHASE: EXTRACT ──
        if "extract" in phases:
            if has_pdf:
                yield sse_phase("extract", "Extracting text from PDF document", "ocr")
                yield sse_token("*[Agent Phase: Extracting vector text from PDF]*\n")
                try:
                    extracted_text = await phase_extract_pdf(req.pdf)
                    yield sse_token(f"\n> Extracted {len(extracted_text)} characters from PDF\n\n")
                    yield sse_phase_result("extract", {"char_count": len(extracted_text)})
                except Exception as e:
                    yield sse_token(f"\n> ⚠ PDF extraction failed: {e}\n\n")
                    extracted_text = f"[PDF extraction failed: {e}]"

            elif has_image:
                # For images: run OCR as supplementary, but vision model is primary
                yield sse_phase("extract", "Running supplementary OCR on image", "ocr")
                yield sse_token("*[Agent Phase: Supplementary OCR Extraction]*\n")
                try:
                    extracted_text = await phase_extract_image(req.images[0])
                    yield sse_token(f"\n> OCR extracted {len(extracted_text)} characters (supplementary)\n")
                    yield sse_token("> Primary analysis will use vision model directly on the image\n\n")
                    yield sse_phase_result("extract", {"char_count": len(extracted_text)})
                except Exception as e:
                    yield sse_token(f"\n> OCR supplementary extraction skipped: {e}\n\n")
                    extracted_text = ""

            phases_completed.append("extract")

        # ── PHASE: RETRIEVE ──
        if "retrieve" in phases:
            yield sse_phase("retrieve", "Searching knowledge base", "embed")
            yield sse_token("*[Agent Phase: RAG Knowledge Retrieval]*\n")

            rag_context, rag_chunks = await phase_retrieve(req.message)

            if rag_chunks:
                yield sse_token(f"\n> Found {len(rag_chunks)} relevant knowledge chunks:\n")
                for i, chunk in enumerate(rag_chunks, 1):
                    yield sse_token(f"> {i}. `{chunk['source']}` (distance: {chunk['distance']})\n")
                yield sse_token("\n")
                yield sse_phase_result("retrieve", {"chunks": rag_chunks})
            else:
                yield sse_token("\n> No relevant documents found in knowledge base\n\n")

            phases_completed.append("retrieve")

        # ── PHASE: REASON ──
        if "reason" in phases:
            # For image tasks: use vision model with actual image
            # For P&ID: use vision model + supplementary OCR in prompt
            # For text tasks: use appropriate text model
            reason_images = None
            if has_image:
                reason_model_key = "vision"
                reason_images = req.images  # pass actual image to vision model
            else:
                reason_model_key = model_key

            reason_cfg = MODELS[reason_model_key]
            yield sse_phase("reason", f"Analyzing with {reason_cfg['display']}", reason_model_key)
            yield sse_token(f"*[Agent Phase: {'Vision Analysis' if has_image else 'Reasoning'} with {reason_cfg['display']}]*\n\n")

            # Build the prompt with all gathered context
            if has_image and is_pid:
                # P&ID: vision model + OCR supplementary
                ocr_block = ""
                if extracted_text and not extracted_text.startswith("["):
                    ocr_block = f"Supplementary OCR text (may contain errors, use image as primary source):\n{extracted_text}"
                else:
                    ocr_block = "OCR could not extract reliable text. Rely on what you see in the image."
                final_prompt = PID_VISION_PROMPT.format(
                    supplementary_ocr=ocr_block,
                    query=req.message,
                )
                run_temp = 0.1
            elif has_image:
                # Generic image: vision model direct
                ocr_block = ""
                if extracted_text and not extracted_text.startswith("["):
                    ocr_block = f"Supplementary OCR text: {extracted_text}"
                final_prompt = GENERIC_VISION_PROMPT.format(
                    supplementary_ocr=ocr_block,
                    query=req.message,
                )
                run_temp = 0.3
            else:
                # Text-only tasks
                context_parts = []
                if extracted_text:
                    context_parts.append(f"[Extracted Document Text]:\n{extracted_text}")
                if rag_context:
                    context_parts.append(f"[Knowledge Base Context]:\n{rag_context}")

                context_block = "\n\n---\n\n".join(context_parts)
                if task_type == "code":
                    final_prompt = (
                        "You are a Python engineering assistant. Return one complete runnable Python "
                        "solution in a fenced ```python block, followed by a short explanation. "
                        "This runs non-interactively in a headless sandbox: NEVER call input(), "
                        "never wait for user input, and use clearly labelled sample values instead.\n\n"
                        f"User request: {req.message}"
                    )
                else:
                    final_prompt = make_general_prompt(req.message, context_block)

                run_temp = 0.7 if task_type == "general" else 0.4

            try:
                verified_response = heat_duty_response(req.message) if task_type == "code" else None
                if verified_response:
                    full_response = verified_response
                    token_count = len(verified_response.split())
                    yield sse_token(verified_response)
                else:
                    async for token in stream_ollama(
                        final_prompt, reason_cfg["tag"], req.context or [],
                        images=reason_images,
                        temperature=run_temp,
                    ):
                        if await request.is_disconnected():
                            return
                        token_count += 1
                        full_response += token
                        yield sse_token(token)
            except (asyncio.CancelledError, httpx.RemoteProtocolError):
                return
            except Exception as e:
                yield sse({"type": "error", "message": str(e)})
                return

            phases_completed.append("reason")

        # ── PHASE: EXECUTE ──
        if "execute" in phases and full_response:
            code_blocks = extract_code_blocks(full_response)
            if code_blocks:
                yield sse_phase("execute", "Executing code in sandbox", "code")
                yield sse_token("\n\n*[Agent Phase: Sandbox Execution]*\n")

                for i, code in enumerate(code_blocks):
                    yield sse_token(f"\n> Running code block {i+1}...\n")
                    result = await phase_execute(code)

                    status_icon = "✅" if result["status"] == "success" else "❌"
                    yield sse_token(f"\n> {status_icon} Exit code: {result['return_code']}\n")

                    if result["stdout"]:
                        yield sse_token(f"\n```\n{result['stdout']}\n```\n")
                    if result["stderr"] and result["status"] != "success":
                        yield sse_token(f"\n> ⚠ stderr: {result['stderr'][:500]}\n")

                    yield sse_phase_result("execute", {
                        "status": result["status"],
                        "return_code": result["return_code"],
                        "stdout": result["stdout"][:1000],
                        "script_file": result["script_file"],
                    })

                phases_completed.append("execute")

        # ── PHASE: ARTIFACT ──
        if "artifact" in phases and full_response:
            artifact_type = detect_artifact_type(req.message)
            if artifact_type:
                yield sse_phase("artifact", f"Generating {artifact_type.upper()} document", "reasoning")
                yield sse_token(f"\n\n*[Agent Phase: Document Generation → {artifact_type.upper()}]*\n")

                try:
                    title = "MRPL " + req.message[:60].title()
                    artifact = await phase_artifact(full_response, title, artifact_type)
                    yield sse_token(f"\n> ✅ Generated: `{artifact['file']}`\n")
                    yield sse({
                        "type": "artifact",
                        "file": artifact["file"],
                        "download_url": artifact["download_url"],
                        "doc_type": artifact["doc_type"],
                    })
                except Exception as e:
                    yield sse_token(f"\n> ⚠ Document generation failed: {e}\n")

                phases_completed.append("artifact")

        # ── DONE ──
        latency = round((time.time() - t0) * 1000)
        yield sse({
            "type": "done",
            "tokens": token_count,
            "latency_ms": latency,
            "phases_completed": phases_completed,
            "task_type": task_type,
            "external_calls": 0,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/models")
async def list_models():
    """Return model routing config and Ollama status."""
    try:
        client = get_client()
        r = await client.get("/api/tags")
        pulled = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pulled = []

    return {
        "models": MODELS,
        "pulled_models": pulled,
        "ollama_url": OLLAMA_BASE_URL,
    }
