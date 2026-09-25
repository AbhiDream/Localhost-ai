"""
OCR router — EasyOCR on CPU, Moondream for P&ID understanding.
No VRAM consumed by OCR itself.
"""
import base64
import json
import os
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import MODELS, OLLAMA_BASE_URL
from routers.network_monitor import record_call

router = APIRouter()
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/extract")
async def extract_text(
    file: UploadFile = File(...),
    question: Optional[str] = Form(None),
):
    """
    1. Save uploaded image
    2. Run EasyOCR for raw text extraction (CPU)
    3. Optionally run Moondream for diagram understanding
    """
    # Save file
    ext = Path(file.filename).suffix or ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / filename
    content = await file.read()
    save_path.write_bytes(content)

    # EasyOCR — CPU only
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False, verbose=False, download_enabled=False)
        results = reader.readtext(str(save_path))
        extracted_text = "\n".join([r[1] for r in results if r[2] > 0.3])
    except Exception as e:
        extracted_text = f"[OCR unavailable: {e}]"

    record_call("ollama_local", f"moondream vision on {filename}")

    # Moondream for diagram understanding
    moondream_response = ""
    if question or extracted_text:
        try:
            img_b64 = base64.b64encode(content).decode()
            q = question or "Describe all components, labels, and connections visible in this diagram."
            payload = {
                "model": MODELS["vision"]["tag"],
                "prompt": f"<image>\n{q}",
                "images": [img_b64],
                "stream": False,
                "options": {"num_predict": 512},
            }
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
                moondream_response = r.json().get("response", "")
        except Exception as e:
            moondream_response = f"[Vision model unavailable: {e}]"

    return {
        "ocr_text": extracted_text,
        "vision_analysis": moondream_response,
        "model_used": MODELS["vision"]["display"],
        "image_saved": filename,
        "external_calls": 0,
    }
