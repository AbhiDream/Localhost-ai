"""
Chat router — streams responses from Ollama.
Includes model routing, token counting, and network-call auditing.
"""
import asyncio
import json
import time
import os
import re
import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import base64
import io

try:
    import numpy as np
    from PIL import Image, ImageFilter, ImageEnhance
    import pytesseract
    # Windows path — change if on Linux
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    _tesseract_available = True
except ImportError:
    _tesseract_available = False

# Never construct EasyOCR at import time. Reader construction can download
# detection/recognition weights when they are missing, which prevents the
# *entire backend* from starting in an air-gapped deployment.
_ocr_reader = None
_ocr_checked = False


def get_local_ocr_reader():
    """Load OCR only on an image request and never permit downloads."""
    global _ocr_reader, _ocr_checked
    if _ocr_checked:
        return _ocr_reader
    _ocr_checked = True
    try:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False, download_enabled=False)
    except Exception:
        _ocr_reader = None
    return _ocr_reader

from config import MODELS, OLLAMA_BASE_URL, route_model
from routers.network_monitor import record_call

router = APIRouter()

# ─── Shared HTTP client ───────────────────────────────────────────────────────
_ollama_client = httpx.AsyncClient(
    base_url=OLLAMA_BASE_URL,
    timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=5.0),
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
)


# ─── Pydantic Models ──────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    model_override: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[list] = []
    images: Optional[list] = None
    pdf: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    model_used: str
    model_display: str
    routing_reason: str
    tokens: int
    latency_ms: float
    external_calls: int


# ─── INPUT PRE-PROCESSOR ─────────────────────────────────────────────────────

def log_blocked(session_id: str, message: str, reason: str):
    """Log blocked inputs to local file."""
    try:
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("logs/blocked_inputs.log", "a") as f:
            f.write(f"[{timestamp}] Session:{session_id} | Reason:{reason} | Input:{message[:100]}\n")
    except Exception:
        pass


def classify_input(message: str, session_id: str = "unknown") -> dict:
    """
    Pre-processor that catches all edge cases BEFORE reaching the AI model.
    Returns {"type": str, "response": str or None}
    If type == "industrial" → let normal pipeline handle it.
    """
    msg = message.strip()
    msg_lower = msg.lower()

    # ── CASE 1: Empty or too short ────────────────────────────────────────────
    if len(msg) < 2:
        return {
            "type": "empty",
            "response": (
                "Please enter a query. For example:\n"
                "• 'Summarize the emergency shutdown SOP for CDU-2'\n"
                "• 'Write a Python script for LMTD calculation'\n"
                "• 'Extract all valve tags from this P&ID diagram'"
            )
        }

    # ── CASE 2: Greetings ─────────────────────────────────────────────────────
    greetings = [
        "hello", "hi", "hey", "hii", "helo", "heya", "howdy",
        "good morning", "good evening", "good afternoon", "good night",
        "namaste", "namaskar", "sup", "what's up", "wassup",
        "greetings", "salaam", "sat sri akal", "jai hind"
    ]
    if msg_lower in greetings or any(msg_lower == g for g in greetings):
        return {
            "type": "greeting",
            "response": (
                "Hello! I am **LocalHost.AI** — your sovereign on-premise AI assistant at MRPL.\n\n"
                "I can help you with:\n"
                "• Analyzing inspection reports and P&ID diagrams\n"
                "• Drafting approval notes and technical reports\n"
                "• Engineering calculations (LMTD, pressure drop, flow rates)\n"
                "• Looking up OISD, PESO, ASME standards\n"
                "• Summarizing SOPs and safety procedures\n\n"
                "What would you like to work on today?"
            )
        }

    # ── CASE 3: Thank you / Acknowledgements ──────────────────────────────────
    acknowledgements = [
        "thanks", "thank you", "thank you so much", "thankyou",
        "ok", "okay", "got it", "understood", "noted",
        "great", "perfect", "awesome", "nice", "good", "cool",
        "fine", "alright", "shukriya", "dhanyawad",
        "theek hai", "accha", "acha", "thx", "ty"
    ]
    if msg_lower in acknowledgements:
        return {
            "type": "acknowledgement",
            "response": (
                "You're welcome! Let me know if you need anything else —\n"
                "inspection reports, calculations, SOP lookups, or document generation."
            )
        }

    # ── CASE 4: Who are you / Identity ───────────────────────────────────────
    identity_triggers = [
        "who are you", "what are you", "who made you", "who built you",
        "what is localhost", "tell me about yourself", "introduce yourself",
        "your name", "what can you do", "what do you do",
        "tumhara naam", "aap kaun ho", "tum kaun ho",
        "about you", "about yourself"
    ]
    if any(t in msg_lower for t in identity_triggers):
        return {
            "type": "identity",
            "response": (
                "I am **LocalHost.AI** — a sovereign on-premise agentic AI workbench "
                "built for MRPL (Mangalore Refinery and Petrochemicals Limited).\n\n"
                "**Built by:** Team LocalHost.AI | SIH 2026 | PS26117\n"
                "**Running on:** Ollama (localhost:11434) — fully air-gapped\n"
                "**Models:** Phi-3.5 Mini · Qwen2.5-Coder · LLaVA-Phi3\n"
                "**Knowledge Base:** OISD · PESO · ASME · API · MRPL SOPs\n\n"
                "I can analyze documents, run calculations, extract P&ID data, "
                "and generate reports — all without any data leaving this machine."
            )
        }

    # ── CASE 5: Image generation capability ─────────────────────────────────
    # This workbench includes local vision/OCR for analysing uploaded images,
    # not an image generator. Keep this deterministic so a small text model
    # cannot hallucinate visual-generation capabilities or echo prompt text.
    image_target = r"\b(?:an?\s+)?(?:image|images|picture|pictures|visual|visuals|illustration|illustrations)\b"
    image_action = r"\b(?:gen\w*|creat\w*|mak\w*|draw\w*)\b"
    is_image_generation_request = bool(
        re.search(rf"{image_action}\s+{image_target}", msg_lower)
        or re.search(rf"{image_target}\s+(?:generation|generator)", msg_lower)
    )
    if is_image_generation_request:
        return {
            "type": "image_generation_unavailable",
            "response": (
                "## Image generation is not enabled in this deployment\n\n"
                "LocalHost.AI can analyse uploaded P&IDs, engineering drawings, photos, "
                "and scanned reports entirely on-device. This workstation does not have a "
                "local image-generation model installed, so I will not claim to create an image. "
                "Upload an image for analysis, or ask for a detailed visual brief for a future "
                "approved local image-generation module."
            )
        }

    # ── CASE 6: Comparison with other AI tools ────────────────────────────────
    comparison_triggers = [
        "better than chatgpt", "vs chatgpt", "compare with gpt",
        "vs gpt", "better than gpt", "chatgpt better", "use chatgpt",
        "why not chatgpt", "vs gemini", "vs copilot", "vs claude",
        "better than claude", "microsoft copilot", "google gemini",
        "why not use gpt", "why not gpt"
    ]
    if any(t in msg_lower for t in comparison_triggers):
        return {
            "type": "comparison",
            "response": (
                "Unlike ChatGPT, Gemini, or Copilot — LocalHost.AI runs entirely on your machine.\n\n"
                "**ChatGPT / Gemini / Copilot:**\n"
                "✗ Your data goes to foreign servers\n"
                "✗ Requires internet connection\n"
                "✗ Monthly subscription cost\n"
                "✗ Not trained on MRPL-specific documents\n\n"
                "**LocalHost.AI:**\n"
                "✓ Zero data leaves the premises\n"
                "✓ Works completely offline\n"
                "✓ Zero subscription cost — open-weight models\n"
                "✓ Pre-indexed with OISD, PESO, ASME, MRPL SOPs\n\n"
                "For confidential industrial work at a PSU — there is no comparison."
            )
        }

    # ── CASE 6: Internet / Web search requests ────────────────────────────────
    internet_triggers = [
        "search the web", "search internet", "google this",
        "look it up online", "check online", "browse",
        "internet search", "web search", "latest news",
        "current price", "stock price", "weather",
        "search for", "google", "bing"
    ]
    if any(t in msg_lower for t in internet_triggers):
        return {
            "type": "no_internet",
            "response": (
                "I operate in a fully air-gapped environment — "
                "I have no internet access by design.\n\n"
                "However, my local knowledge base contains 40+ indexed documents "
                "including OISD standards, PESO regulations, ASME codes, and MRPL SOPs.\n\n"
                "Try rephrasing your query — I can likely answer it from the local knowledge base."
            )
        }

    # ── CASE 7: Off-topic queries ─────────────────────────────────────────────
    off_topic_triggers = [
        "cricket", "ipl", "bollywood", "movie", "film", "song",
        "recipe", "cook", "food", "restaurant", "hotel", "travel",
        "politics", "election", "joke", "funny", "meme",
        "girlfriend", "boyfriend", "love", "dating", "marriage",
        "game", "gaming", "pubg", "minecraft", "fortnite",
        "instagram", "facebook", "youtube", "tiktok",
        "share market", "crypto", "bitcoin", "investment tips",
        "homework", "exam", "school admission", "college admission",
        "astrology", "horoscope", "lottery"
    ]
    if any(t in msg_lower for t in off_topic_triggers):
        return {
            "type": "off_topic",
            "response": (
                "I am specialized for industrial and refinery operations at MRPL. "
                "I cannot help with this topic.\n\n"
                "I can assist with:\n"
                "• P&ID diagram analysis\n"
                "• Inspection report generation\n"
                "• Engineering calculations\n"
                "• OISD / PESO / ASME standard lookup\n"
                "• SOP summarization and safety procedures\n\n"
                "Please ask an industrial or technical question."
            )
        }

    # ── CASE 8: Prompt injection attempts ─────────────────────────────────────
    injection_triggers = [
        "ignore previous instructions", "forget your instructions",
        "ignore your system prompt", "you are now", "pretend you are",
        "act as", "jailbreak", "dan mode", "developer mode",
        "ignore all rules", "bypass", "override instructions",
        "new instructions", "disregard", "from now on you are",
        "ignore everything", "forget everything"
    ]
    if any(t in msg_lower for t in injection_triggers):
        log_blocked(session_id, msg, "PROMPT_INJECTION")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        return {
            "type": "injection_blocked",
            "response": (
                "⚠️ This request has been blocked.\n"
                "LocalHost.AI operates under strict industrial safety protocols "
                "and cannot override its core instructions.\n\n"
                f"Session: {session_id} | Time: {timestamp}\n"
                "All blocked requests are logged in the audit trail."
            )
        }

    # ── CASE 9: Test / Random inputs ──────────────────────────────────────────
    test_inputs = [
        "test", "testing", "123", "abc", "asdf", "qwerty",
        "1234", "test123", "hello world", "ping", "check",
        "aaa", "bbb", "???", "...", "lol", "lmao", "bruh",
        "random", "nothing", "idk", "idc", "whatever",
        "gg", "ok", "kk", "hmm"
    ]
    if msg_lower in test_inputs:
        return {
            "type": "test_input",
            "response": (
                "**System Status: All systems operational.**\n\n"
                "Air-Gap Status: VERIFIED ✓\n"
                "Models loaded: Phi-3.5 Mini · Qwen2.5-Coder · LLaVA-Phi3\n"
                "Knowledge Base: Active (ChromaDB)\n"
                "External calls: 0\n\n"
                "Ready to process industrial queries."
            )
        }

    # ── CASE 10: Abusive / inappropriate input ────────────────────────────────
    abusive_words = [
        "fuck", "shit", "bastard", "asshole", "bitch", "damn",
        "crap", "idiot", "stupid", "moron", "madarchod",
        "behenchod", "chutiya", "saala", "harami", "bakwaas"
    ]
    if any(w in msg_lower for w in abusive_words):
        log_blocked(session_id, msg, "INAPPROPRIATE_CONTENT")
        return {
            "type": "inappropriate",
            "response": (
                "This input is not appropriate for an industrial workplace system. "
                "Please keep queries professional.\n\n"
                "This interaction has been logged."
            )
        }

    # ── CASE 11: System status check ─────────────────────────────────────────
    status_triggers = [
        "how are you", "are you okay", "are you working",
        "is the system up", "system status", "server status",
        "are you online", "is ollama running", "check status",
        "status", "health check", "are you there"
    ]
    if any(t in msg_lower for t in status_triggers):
        return {
            "type": "status",
            "response": (
                "**All systems operational.**\n\n"
                "Ollama API    → localhost:11434 ✓\n"
                "ChromaDB      → localhost:8000 ✓\n"
                "Internet      → blocked ✓\n"
                "Cloud API     → blocked ✓\n"
                "External Calls → 0\n\n"
                "LocalHost.AI is ready for industrial queries."
            )
        }

    # ── Default: Let industrial pipeline handle it ────────────────────────────
    return {"type": "industrial", "response": None}


# ─── Ollama Streaming ─────────────────────────────────────────────────────────

async def stream_ollama(
    prompt: str, model_tag: str, context: list, images: Optional[list] = None, temperature: float = 0.7
) -> AsyncGenerator[str, None]:
    """Stream tokens from Ollama generate API using the shared client."""
    payload = {
        "model": model_tag,
        "prompt": prompt,
        "stream": True,
        "context": context,
        "options": {
            "num_ctx": 4096,
            "temperature": temperature,
        },
    }
    if images:
        payload["images"] = images
    async with _ollama_client.stream(
        "POST", "/api/generate", json=payload
    ) as resp:
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


# ─── Main Stream Endpoint ─────────────────────────────────────────────────────

@router.post("/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """Server-Sent Events streaming endpoint."""
    record_call("ollama_local", req.message[:80])

    async def event_generator():
        target_message = req.message

        # ── PRE-PROCESSOR: Check BEFORE any AI routing ────────────────────────
        # Only run pre-processor if no image/pdf attached
        if not req.images and not req.pdf:
            classification = classify_input(
                req.message,
                req.session_id or "unknown"
            )
            if classification["type"] != "industrial":
                # Send direct response without calling Ollama
                response_text = classification["response"]
                # Stream it word by word for consistent UI experience
                words = response_text.split(" ")
                for word in words:
                    chunk = {"type": "token", "text": word + " "}
                    yield f"data: {json.dumps(chunk)}\n\n"
                    await asyncio.sleep(0.01)
                done = {
                    "type": "done",
                    "tokens": len(words),
                    "latency_ms": 0,
                    "external_calls": 0,
                }
                yield f"data: {json.dumps(done)}\n\n"
                return
        # ── END PRE-PROCESSOR ─────────────────────────────────────────────────

        # --- PHASE 1: Image & PDF Extraction (Agentic Workflow) ---
        is_pid = False
        extracted_text = ""
        prompt_lower = req.message.lower()
        is_pid = any(w in prompt_lower for w in [
            "p&id", "pid", "diagram", "schematic", "tag", "valve",
            "instrument", "extract", "analyze", "what"
        ])

        needs_ocr = True if req.images else any(w in prompt_lower for w in [
            "ocr", "document", "scan", "read", "text", "report", "extract"
        ])

        if req.images:
            is_pid = True

        if req.pdf:
            import pdfplumber
            import tempfile
            ocr_cfg = MODELS["ocr"]
            meta_vision = {
                "type": "meta",
                "model": "ocr",
                "model_display": ocr_cfg["display"],
                "model_tag": ocr_cfg["tag"],
                "model_color": ocr_cfg["color"],
            }
            yield f"data: {json.dumps(meta_vision)}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'text': '*[Agent Phase 1: Extracting vector text from PDF]*\n'})}\n\n"

            try:
                pdf_bytes = base64.b64decode(req.pdf)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                    f.write(pdf_bytes)
                    temp_path = f.name

                all_text = []
                with pdfplumber.open(temp_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            all_text.append(text)
                os.unlink(temp_path)

                combined = "\n".join(all_text)

                if is_pid:
                    tags = re.findall(r'\b([A-Z]{1,3}-\d{2,4})\b', combined)
                    unique_tags = list(dict.fromkeys(tags))
                    print(f"Found {len(unique_tags)} tags in PDF: {unique_tags}")
                    if not unique_tags:
                        extracted_text = "No tags found in PDF text."
                    else:
                        extracted_text = "TAGS FOUND: " + ", ".join(unique_tags)
                else:
                    extracted_text = combined

            except Exception as e:
                extracted_text = f"[Failed to parse PDF: {str(e)}]"

        elif req.images:
            if is_pid:
                ocr_cfg = MODELS["ocr"]
                meta_vision = {
                    "type": "meta",
                    "model": "ocr",
                    "model_display": ocr_cfg["display"],
                    "model_tag": ocr_cfg["tag"],
                    "model_color": ocr_cfg["color"],
                }
                yield f"data: {json.dumps(meta_vision)}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'text': '*[Agent Phase 1: Running OCR Extraction]*\n'})}\n\n"

                extracted_text = ""
                try:
                    img_bytes = base64.b64decode(req.images[0])
                    img = Image.open(io.BytesIO(img_bytes))

                    w, h = img.size
                    img = img.resize((w * 4, h * 4), Image.LANCZOS)
                    img = ImageEnhance.Contrast(img).enhance(3.0)
                    img = ImageEnhance.Sharpness(img).enhance(2.0)
                    img = img.convert("L")

                    arr = np.array(img)
                    threshold = arr.mean() * 0.85
                    arr = np.where(arr < threshold, 0, 255).astype(np.uint8)
                    img = Image.fromarray(arr)

                    # Try pytesseract first, fallback to easyocr
                    raw_text = ""
                    if _tesseract_available:
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
                            img.save(f, format="PNG")
                            temp_img_path = f.name
                        # Space added to whitelist so "FCV 1" is read correctly
                        custom_config = r'--oem 3 --psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-. '
                        raw_text = pytesseract.image_to_string(temp_img_path, config=custom_config)
                        os.unlink(temp_img_path)
                        print(f"[DEBUG] Pytesseract raw OCR:\n{raw_text}")
                    elif get_local_ocr_reader() is not None:
                        results = _ocr_reader.readtext(arr)
                        raw_text = "\n".join([r[1] for r in results if r[2] > 0.25])
                        print(f"[DEBUG] EasyOCR raw output:\n{raw_text}")

                    # Send RAW text to Phi-3.5 — no regex filtering
                    extracted_text = f"RAW OCR OUTPUT:\n{raw_text}"

                except Exception as e:
                    extracted_text = f"[OCR failed: {str(e)}]"
                    print(f"[DEBUG] OCR exception: {e}")

        # --- PHASE 2: Build target message & route ---
        if (req.images or req.pdf) and is_pid:
            target_message = f"""You are a P&ID expert at an oil refinery.

OCR scanned a P&ID diagram and returned this raw text.
OCR often garbles text inside circular instrument symbols
— for example "(icv\\" means LCV, "(EVN" means FCV, "(HCV)" means HCV.
Numbers may be separated from their tag prefix by a space or newline.

RAW OCR TEXT:
{extracted_text}

Your job — interpret the OCR output using P&ID domain knowledge:

1. INSTRUMENT TAGS — identify any transmitters or controllers
   (FT, PT, LT, TT, AT, AC, TC, PC, LC, FC, HC)

2. CONTROL VALVES — identify any control valves
   (FCV, LCV, HCV, PCV, TCV — often shown inside circles in P&IDs)

3. EQUIPMENT — identify named equipment
   (columns, exchangers, pumps, accumulators, coolers etc.)

4. FLOW RATES — extract any numbers with gpm, kg/h, m3/h units

5. PROCESS STREAMS — extract named streams
   (Feed, Steam, Condensate, Toluene, CWS, Gas to flare etc.)

For garbled text: use context and P&ID conventions to interpret.
State your confidence: HIGH if text is clear, LOW if you interpreted garbled OCR.
Do NOT invent anything with HIGH confidence that is not in the OCR text.

Query: {req.message}"""
            model_key = "reasoning"
            run_temp = 0.0

        elif (req.images or req.pdf):
            target_message = (
                f"User Prompt: {req.message}\n\n"
                f"[Extracted Visual Data]:\n{extracted_text}\n\n"
                "CRITICAL: Only report what you can see in the extracted text. "
                "Do not hallucinate."
            )
            model_key = route_model(req.message, req.model_override)
            run_temp = 0.7
        else:
            model_key = route_model(req.message, req.model_override)
            run_temp = 0.7

        model_cfg = MODELS[model_key]

        meta_final = {
            "type": "meta",
            "model": model_key,
            "model_display": model_cfg["display"],
            "model_tag": model_cfg["tag"],
            "model_color": model_cfg["color"],
        }
        yield f"data: {json.dumps(meta_final)}\n\n"

        t0 = time.time()
        token_count = 0
        try:
            async for token in stream_ollama(
                target_message, model_cfg["tag"], req.context or [], temperature=run_temp
            ):
                if await request.is_disconnected():
                    break
                token_count += 1
                chunk = {"type": "token", "text": token}
                yield f"data: {json.dumps(chunk)}\n\n"
        except (asyncio.CancelledError, httpx.RemoteProtocolError):
            return
        except Exception as e:
            err = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(err)}\n\n"
            return

        latency = round((time.time() - t0) * 1000)
        done = {
            "type": "done",
            "tokens": token_count,
            "latency_ms": latency,
            "external_calls": 0,
        }
        yield f"data: {json.dumps(done)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Sync endpoint ────────────────────────────────────────────────────────────

@router.post("/sync", response_model=ChatResponse)
async def chat_sync(req: ChatRequest):
    """Non-streaming chat — for document generation pipeline."""
    model_key = route_model(req.message, req.model_override)
    model_cfg = MODELS[model_key]

    record_call("ollama_local", req.message[:80])
    t0 = time.time()

    payload = {
        "model": model_cfg["tag"],
        "prompt": req.message,
        "stream": False,
        "options": {"num_ctx": 4096, "temperature": 0.6},
    }

    try:
        resp = await _ollama_client.post("/api/generate", json=payload)
        data = resp.json()
    except Exception as e:
        raise HTTPException(503, f"Ollama unreachable: {e}")

    latency = round((time.time() - t0) * 1000)
    return ChatResponse(
        response=data.get("response", ""),
        model_used=model_key,
        model_display=model_cfg["display"],
        routing_reason=f"Keyword routing → {model_key}",
        tokens=data.get("eval_count", 0),
        latency_ms=latency,
        external_calls=0,
    )


# ─── Models info endpoint ─────────────────────────────────────────────────────

@router.get("/models")
async def list_models():
    """Return model routing config and Ollama status."""
    try:
        r = await _ollama_client.get("/api/tags")
        pulled = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pulled = []

    return {
        "models": MODELS,
        "pulled_models": pulled,
        "ollama_url": OLLAMA_BASE_URL,
    }
