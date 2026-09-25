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
import math
import os
import re
import subprocess
import sys
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
    """Extract text from a PDF, with on-device OCR for scanned pages."""
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

            # Inspection reports are often scans, so text extraction can be
            # empty even though the report visibly contains findings. Run OCR
            # in a bounded child process: a heavy OCR job must never terminate
            # the live FastAPI service and cause a frontend 502.
            if len("\n".join(all_text).strip()) < 80:
                try:
                    worker = Path(__file__).with_name("pdf_ocr_worker.py")
                    completed = await asyncio.to_thread(
                        subprocess.run,
                        [sys.executable, "-E", str(worker), temp_path],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=45,
                        check=False,
                    )
                    if completed.returncode == 0:
                        # Some OCR backends print a CPU status line before
                        # our JSON result. Read the final valid JSON line.
                        for line in reversed(completed.stdout.splitlines()):
                            try:
                                payload = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if payload.get("text"):
                                return payload["text"]
                            break
                except Exception:
                    # The evidence gate below will safely decline factual
                    # drafting if local OCR is unavailable or finds no text.
                    pass
    finally:
        os.unlink(temp_path)

    return "\n\n".join(
        f"[Source: attached PDF, page {index}]\n{text}"
        for index, text in enumerate(all_text, start=1)
    )


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
        reader = easyocr.Reader(["en"], gpu=False, verbose=False, download_enabled=False)
        results = reader.readtext(arr)
        extracted = "\n".join([r[1] for r in results if r[2] > 0.25])
        return extracted if extracted else "[No text detected in image]"
    except Exception as e:
        return f"[OCR failed: {e}]"


# ── Phase: RETRIEVE ───────────────────────────────────────────

async def phase_retrieve(query: str, n_results: int = 3) -> tuple[str, list]:
    """Search knowledge base for relevant context. Returns (context_str, chunks)."""
    # A named standard is a document identifier, not a semantic hint. Resolve
    # it from the bundled local source *before* vector search so OISD-116 can
    # never be answered from OISD-118 or another similar standard.
    standard = requested_standard(query)
    if standard:
        return local_text_retrieve(query, n_results, source_filter=standard)

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

        # A vector store always returns its nearest neighbours, even when none
        # are genuinely relevant. Require local lexical evidence as a second
        # gate, so a question such as "current market price of crude oil" is
        # not treated as supported merely because a manual mentions crude oil.
        meaningful_terms = _meaningful_query_terms(query)
        minimum_overlap = max(1, math.ceil(len(meaningful_terms) / 2))
        relevant = [
            (document, metadata, distance)
            for document, metadata, distance in zip(docs, metas, dists)
            if sum(term in document.lower() for term in meaningful_terms) >= minimum_overlap
        ]
        if not relevant:
            return "", []
        docs, metas, dists = map(list, zip(*relevant))

        # Preserve provenance on every vector-store chunk. The model receives
        # a source marker, not an anonymous paragraph it can misattribute.
        context_str = "\n\n---\n\n".join(
            f"[Source: {m.get('source', 'unknown')}{f', page {m.get('page')}' if m.get('page') else ''}]\n{d}"
            for d, m in zip(docs, metas)
        )
        chunks = [
            {"text": d[:200], "distance": round(dist, 4), "source": m.get("source", "unknown"), "page": m.get("page")}
            for d, dist, m in zip(docs, dists, metas)
        ]
        return context_str, chunks
    except Exception as e:
        return local_text_retrieve(query, n_results)


def requested_standard(query: str) -> str | None:
    """Return a canonical standard identifier such as ``OISD-116``."""
    match = re.search(r"\b(OISD|API|IS)\s*[- ]?\s*(\d{2,4})\b", query, re.I)
    if not match:
        return None
    return f"{match.group(1).upper()}-{match.group(2)}"


def _meaningful_query_terms(query: str) -> set[str]:
    """Extract content words used to decide if a RAG match is really relevant."""
    stop_words = {
        "about", "according", "after", "also", "and", "are", "can", "could",
        "does", "for", "from", "have", "how", "into", "is", "local", "me",
        "of", "on", "please", "should", "tell", "that", "the", "this", "to",
        "what", "when", "where", "which", "with", "would", "you", "your",
    }
    return {
        term for term in re.findall(r"[a-z0-9]+", query.lower())
        if len(term) > 2 and term not in stop_words
    }


def _source_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", value.upper()).strip("-")


def _source_passages(text: str) -> list[tuple[str | None, str]]:
    """Split locally extracted standards into page-aware passages."""
    pieces = re.split(r"(?=---\s*PAGE\s*\d+[^\n]*---)", text, flags=re.I)
    passages = []
    for piece in pieces:
        page_match = re.search(r"---\s*PAGE\s*(\d+)[^\n]*---", piece, flags=re.I)
        page = page_match.group(1) if page_match else None
        cleaned = re.sub(r"---\s*PAGE\s*\d+[^\n]*---", "", piece, flags=re.I).strip()
        if cleaned:
            passages.append((page, cleaned))
    return passages or [(None, text)]


def local_text_retrieve(
    query: str, n_results: int = 3, source_filter: str | None = None,
) -> tuple[str, list]:
    """Offline lexical retrieval with optional exact source enforcement."""
    docs_dir = Path(__file__).resolve().parents[2] / "downloaded_docs"
    if not docs_dir.is_dir():
        return "", []

    terms = _meaningful_query_terms(query)
    minimum_overlap = max(1, math.ceil(len(terms) / 2))
    paths = list(docs_dir.glob("*.txt"))
    if source_filter:
        source_key = _source_key(source_filter)
        paths = [path for path in paths if source_key in _source_key(path.stem)]
        if not paths:
            return "", []

    candidates = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for page, passage in _source_passages(text):
            matching_terms = sum(term in passage.lower() for term in terms)
            score = sum(passage.lower().count(term) for term in terms)
            score += sum(5 for term in terms if term in path.stem.lower())
            if matching_terms >= minimum_overlap or source_filter:
                candidates.append((score, path, page, passage))

    if not candidates:
        return "", []
    selected = sorted(candidates, key=lambda item: item[0], reverse=True)[:n_results]
    result_chunks = []
    for score, path, page, passage in selected:
        words = passage.split()
        # Return the best local paragraph window, not the introduction.
        windows = [words[i:i + 220] for i in range(0, len(words), 140)] or [[]]
        def passage_score(passage):
            passage_text = " ".join(passage).lower()
            return sum(passage_text.count(term) for term in terms)
        excerpt = " ".join(max(windows, key=passage_score))
        result_chunks.append({"text": excerpt, "distance": 0.0, "source": path.name, "page": page})
    context = "\n\n---\n\n".join(
        f"[Source: {item['source']}{f', page {item['page']}' if item['page'] else ''}]\n{item['text']}"
        for item in result_chunks
    )
    return context, result_chunks


def named_standard_evidence_response(standard: str, chunks: list[dict]) -> str:
    """Return only local excerpts for a specifically named standard.

    Standard-number questions are high-stakes knowledge lookups. An extractive
    answer is more useful (and safer) than a fluent answer that may blend in a
    nearby standard, model memory, or an unsupported design requirement.
    """
    excerpts = []
    for chunk in chunks:
        page = f", page {chunk['page']}" if chunk.get("page") else ""
        excerpts.append(f"[Source: {chunk['source']}{page}]\n{chunk['text']}")
    return (
        f"## {standard} — local source evidence\n\n"
        "The following is retrieved from the exact locally indexed standard. "
        "No other standard or external source was used.\n\n"
        + "\n\n---\n\n".join(excerpts)
    )


def grounded_comparison_prompt(
    request: str, attached_evidence: str, standard_evidence: str, standard: str,
) -> str:
    """Compare an attachment against one exact local standard without blending sources."""
    return (
        "You are LocalHost.AI performing a source-bound comparison. Compare ONLY "
        "the attached document evidence with the exact local standard evidence below. "
        "Do not use model memory, other standards, or unstated domain knowledge. "
        "Do not claim compliance/non-compliance unless both sources explicitly support it. "
        "If the documents concern different subjects or a fact is absent, state "
        "'Not established from the supplied sources.'\n\n"
        f"ATTACHED DOCUMENT EVIDENCE:\n{attached_evidence}\n\n"
        f"EXACT {standard} LOCAL EVIDENCE:\n{standard_evidence}\n\n"
        f"REQUEST: {request}\n\n"
        "Return exactly these sections:\n"
        "## Scope of each source\n"
        "## Common or related points\n"
        "## Differences / applicability limits\n"
        "## Conclusion\n\n"
        "Keep the comparison under 220 words; prefer an applicability limit over speculation.\n\n"
        "Every factual sentence must include its relevant [Source: ..., page ...] marker."
    )


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
            f"{base}\n\nYou must use ONLY the evidence below for factual claims. "
            "Never combine sources or fill missing details from general knowledge. "
            "For every finding, include its [Source: filename, page] marker. "
            "If evidence is absent, write 'Not available in the supplied source.'\n\n"
            "Evidence:\n"
            f"{context_block}\n\nUser request: {user_message}\n\n"
            "Give a concise, structured, evidence-grounded answer."
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
    if normalized in {"thanks", "thank you", "okay", "ok", "got it", "understood"}:
        return "You’re welcome. I’m ready for a local document, standards, vision, or coding task."
    if normalized in {"how are you", "are you working", "are you there", "system status"}:
        return "LocalHost.AI is ready. It uses only local services and does not send your prompt or files outside this machine."
    return None


def capability_response(message: str) -> str | None:
    """Keep common product questions deterministic and concise."""
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    triggers = (
        "who are you", "what are you", "what can you do", "what do you do",
        "tell me about yourself", "what is localhost.ai", "what is localhost ai",
    )
    if not any(trigger in normalized for trigger in triggers):
        return None
    return (
        "## LocalHost.AI capabilities\n\n"
        "- Search approved local standards and SOPs with source citations\n"
        "- Summarize uploaded PDFs and inspection reports locally\n"
        "- Analyze uploaded drawings, P&IDs, photos, and scans\n"
        "- Draft internal reports and write Python engineering utilities\n\n"
        "All inference and document handling remain on this workstation."
    )


def no_local_evidence_response(message: str) -> str:
    """Fail closed for factual questions outside the approved local sources."""
    return (
        "## Local evidence not available\n\n"
        "I could not find approved local source material for this request, so I will not guess "
        "or generate an unverified factual answer. Attach the relevant document, or ask about an "
        "indexed local standard/SOP. I can still write code or prepare a draft when you provide the "
        "required inputs."
    )


def live_data_response(message: str) -> str | None:
    """Decline information that an air-gapped workbench cannot verify live."""
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    live_data_phrases = (
        "current price", "market price", "stock price", "share price",
        "exchange rate", "latest news", "breaking news", "weather forecast",
        "weather today", "live score", "current score", "current election",
    )
    if not any(phrase in normalized for phrase in live_data_phrases):
        return None
    return (
        "## Live data is unavailable by design\n\n"
        "LocalHost.AI is air-gapped and does not access the internet or external market feeds. "
        "I cannot verify live prices, news, weather, or scores. Upload an approved local report "
        "if you need analysis of a specific dataset."
    )


def image_generation_response(message: str) -> str | None:
    """Answer image-creation requests without sending them to a text model.

    This installation contains local vision/OCR models for understanding an
    uploaded scan, photograph or P&ID.  It does not ship an image-generation
    model, so forwarding the request to a general text model only invites it
    to invent capabilities or echo unrelated prompt text.
    """
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    image_target = r"\b(?:an?\s+)?(?:image|images|picture|pictures|visual|visuals|illustration|illustrations)\b"
    # ``gen\w*`` intentionally catches ordinary spelling slips such as
    # "genarte image". It is paired with an explicit visual target, so it
    # does not catch unrelated words such as "general".
    image_action = r"\b(?:gen\w*|creat\w*|mak\w*|draw\w*)\b"
    if not (
        re.search(rf"{image_action}\s+{image_target}", normalized)
        or re.search(rf"{image_target}\s+(?:generation|generator)", normalized)
    ):
        return None
    return (
        "## Image generation is not enabled in this deployment\n\n"
        "LocalHost.AI can analyze uploaded P&IDs, engineering drawings, photos, "
        "and scanned reports entirely on-device. This workstation does not have a "
        "local image-generation model installed, so I will not claim to create an image. "
        "You can upload an image for analysis, or ask me to draft a detailed visual brief "
        "for a future approved local image-generation module."
    )


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
    lmtd = (delta_t1 - delta_t2) / math.log(delta_t1 / delta_t2)
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


def expression_calculator_response() -> str:
    """A safe local terminal calculator for arithmetic expressions."""
    return '''## Interactive expression calculator

This accepts an expression such as `24 + 56 * 4` and follows normal arithmetic precedence. It permits only numbers, parentheses, `+`, `-`, `*`, `/`, `//`, `%`, and `**`; it does not use Python `eval()`.

```python
import ast
import operator


BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def evaluate_expression(expression: str) -> float | int:
    """Evaluate a numeric arithmetic expression without eval()."""
    tree = ast.parse(expression, mode="eval")

    def visit(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
            return BIN_OPS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPS:
            return UNARY_OPS[type(node.op)](visit(node.operand))
        raise ValueError("Use numbers, parentheses, and + - * / // % ** only.")

    return visit(tree.body)


if __name__ == "__main__":
    expression = input("Enter an arithmetic expression: ")
    try:
        print(f"Result: {evaluate_expression(expression)}")
    except (SyntaxError, ValueError, ZeroDivisionError) as error:
        print(f"Invalid expression: {error}")
```

Example: entering `24+56*4` prints `Result: 248`. This script intentionally runs in a local terminal because it requests user input.''' 


def requests_interactive_code(message: str) -> bool:
    """Whether the user explicitly asks for a program that reads from stdin."""
    lower = message.lower()
    return any(term in lower for term in (
        "input from user", "take input", "user input", "interactive input",
        "using input", "use input()", "use input",
    ))


def calculator_response(message: str) -> str | None:
    """Supply deterministic calculator code only for well understood requests."""
    lower = message.lower()
    if "calculator" not in lower:
        return None
    if "lmtd" in lower or "heat duty" in lower:
        return (
            "## Calculation inputs required\n\n"
            "To calculate LMTD/heat duty safely, provide hot and cold inlet/outlet "
            "temperatures, the flow rate and stream, fluid specific heat, and flow arrangement. "
            "No calculation has been performed because the required engineering inputs are incomplete."
        )
    # Do not discard a real user requirement behind the generic demo fallback.
    # These requests need expression parsing and intentionally use input().
    if (
        any(term in lower for term in ("input", "expression", "multiple operation", "multiple operations", "at once"))
        or bool(re.search(r"\d\s*[+\-*/%]\s*\d", message))
    ):
        return expression_calculator_response()
    return '''## Verified four-function calculator

```python
def calculate(operation: str, left: float, right: float) -> float:
    operations = {
        "add": lambda: left + right,
        "subtract": lambda: left - right,
        "multiply": lambda: left * right,
        "divide": lambda: left / right,
    }
    if operation not in operations:
        raise ValueError("operation must be add, subtract, multiply, or divide")
    if operation == "divide" and right == 0:
        raise ZeroDivisionError("division by zero is not allowed")
    return operations[operation]()


if __name__ == "__main__":
    examples = [("add", 18, 6), ("subtract", 18, 6), ("multiply", 18, 6), ("divide", 18, 6)]
    for operation, left, right in examples:
        print(f"{operation}: {calculate(operation, left, right)}")
```

The script is non-interactive so it can be executed and verified safely in the local sandbox.'''


def grounded_document_prompt(user_message: str, evidence: str) -> str:
    """Constrain inspection/report writing to extracted or retrieved evidence."""
    if not evidence.strip():
        return (
            "## Evidence required\n\n"
            "No inspection report or local knowledge evidence was supplied. "
            "A factual approval note cannot be drafted safely. Attach the inspection report "
            "or ask a question covered by the indexed local knowledge base."
        )
    return (
        "You are LocalHost.AI preparing an internal industrial document. Use ONLY the "
        "EVIDENCE below. Do not invent measurements, dates, equipment conditions, causes, "
        "or recommendations. For each factual statement include the source marker exactly as "
        "provided. When required information is missing, write 'Not available in the supplied source.'\n\n"
        f"EVIDENCE:\n{evidence}\n\n"
        f"REQUEST: {user_message}\n\n"
        "Write sections: Evidence Summary, Findings, Risk / Data Gaps, Recommended Next Action."
    )


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
        # A reasoning response contains both explanation and a fenced program.
        # Only persist the actual program: otherwise a downloaded .py file can
        # begin with prose and fail before the user ever runs it.
        code_blocks = extract_code_blocks(content)
        script_content = max(code_blocks, key=len) if code_blocks else content
        path = build_python_script(title, script_content)
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
        deterministic_response = None
        if not has_image and not has_pdf:
            deterministic_response = (
                greeting_response(req.message)
                or capability_response(req.message)
                or live_data_response(req.message)
                or image_generation_response(req.message)
            )
        if deterministic_response:
            yield sse_token(deterministic_response)
            yield sse({
                "type": "done", "tokens": len(deterministic_response.split()),
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
                    extracted_text = ""

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
                    page = f", page {chunk['page']}" if chunk.get("page") else ""
                    yield sse_token(f"> {i}. `{chunk['source']}{page}` (distance: {chunk['distance']})\n")
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
            named_standard = requested_standard(req.message)
            context_block = ""
            if not has_image:
                context_parts = []
                if extracted_text:
                    context_parts.append(extracted_text)
                if rag_context:
                    context_parts.append(f"[Knowledge Base Context]:\n{rag_context}")
                context_block = "\n\n---\n\n".join(context_parts)

            missing_named_standard = bool(named_standard and not rag_context)
            attached_standard_comparison = bool(
                has_pdf and named_standard and extracted_text and rag_context
            )
            if named_standard and not rag_context:
                # A standard number must resolve to that exact local file. Do
                # not ask the model to guess from its training data or from a
                # neighbouring standard such as OISD-118.
                final_prompt = (
                    f"## Local source not found\n\n"
                    f"`{named_standard}` is not available in this local knowledge base. "
                    "I have not used another standard as a substitute. Add the approved local "
                    "source and retry."
                )
            elif attached_standard_comparison:
                # Exact-standard retrieval is preserved, but an attachment
                # changes the task from a lookup into a two-source comparison.
                final_prompt = grounded_comparison_prompt(
                    req.message, extracted_text, rag_context, named_standard,
                )
                run_temp = 0.2
            elif has_image and is_pid:
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
                if task_type == "code":
                    execution_constraint = (
                        "The user explicitly requested interactive input. Return a runnable local-terminal "
                        "script using input() and state that it must not be executed in the headless sandbox."
                        if requests_interactive_code(req.message)
                        else "This runs non-interactively in a headless sandbox: NEVER call input(), "
                        "never wait for user input, and use clearly labelled sample values instead."
                    )
                    final_prompt = (
                        "You are a Python engineering assistant. Return one complete runnable Python "
                        "solution in a fenced ```python block, followed by a short explanation. "
                        f"{execution_constraint}\n\n"
                        f"User request: {req.message}"
                    )
                elif task_type == "document":
                    final_prompt = grounded_document_prompt(req.message, context_block)
                else:
                    final_prompt = make_general_prompt(req.message, context_block)

                run_temp = 0.7 if task_type == "general" else 0.4

            try:
                verified_response = None
                if missing_named_standard:
                    verified_response = final_prompt
                elif has_pdf and not extracted_text:
                    verified_response = (
                        "## Readable evidence required\n\n"
                        "No text could be extracted from this PDF using the local reader/OCR worker. "
                        "The backend remains available, but a factual summary or comparison cannot be "
                        "produced without readable source evidence. Try a clearer scan or the first three pages."
                    )
                elif named_standard and rag_chunks and not has_pdf:
                    verified_response = named_standard_evidence_response(named_standard, rag_chunks)
                elif task_type == "code":
                    verified_response = heat_duty_response(req.message) or calculator_response(req.message)
                elif task_type == "document" and not context_block:
                    verified_response = grounded_document_prompt(req.message, "")
                elif (
                    task_type in {"general", "knowledge"}
                    and not has_image
                    and not has_pdf
                    and not rag_context
                ):
                    # A factual question without uploaded or locally retrieved
                    # evidence must not be handed to a small model to improvise.
                    verified_response = no_local_evidence_response(req.message)
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
                if any("input(" in code for code in code_blocks):
                    yield sse_token(
                        "\n\n> ℹ Interactive input was requested, so this program was not run in the "
                        "headless sandbox. Download or copy it and run it in a local terminal.\n"
                    )
                    phases_completed.append("execute-skipped-interactive")
                    code_blocks = []
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
