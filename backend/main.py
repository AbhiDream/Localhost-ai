"""
MRPL AI Workbench — FastAPI Backend
All inference routes through local Ollama. Zero external calls.
"""
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import OLLAMA_BASE_URL
from routers import agent, chat, documents, ocr, rag, sandbox, network_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared httpx clients — open on startup, close on shutdown."""
    app.state.health_client = httpx.AsyncClient(
        base_url=OLLAMA_BASE_URL,
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
    )
    # Re-initialize the chat router's shared client at startup
    chat._ollama_client = httpx.AsyncClient(
        base_url=OLLAMA_BASE_URL,
        timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=5.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    yield
    await app.state.health_client.aclose()
    await chat._ollama_client.aclose()


app = FastAPI(
    title="MRPL AI Workbench",
    description="Self-hosted, air-gapped AI workbench for oil-refinery knowledge work",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(agent.router,          prefix="/api/agent",     tags=["Agent"])
app.include_router(chat.router,           prefix="/api/chat",      tags=["Chat"])
app.include_router(documents.router,      prefix="/api/documents", tags=["Documents"])
app.include_router(ocr.router,            prefix="/api/ocr",       tags=["OCR"])
app.include_router(rag.router,            prefix="/api/rag",       tags=["RAG"])
app.include_router(sandbox.router,        prefix="/api/sandbox",   tags=["Sandbox"])
app.include_router(network_monitor.router, prefix="/api/network",  tags=["Network"])

# Ensure directories exist
Path("outputs").mkdir(exist_ok=True)
Path("uploads").mkdir(exist_ok=True)
Path("chroma_db").mkdir(exist_ok=True)

@app.get("/outputs/{filename:path}")
async def download_output_file(filename: str):
    file_path = Path("outputs") / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=file_path.name, content_disposition_type="attachment")


@app.get("/")
async def root():
    return {"status": "MRPL AI Workbench running", "version": "2.0.0", "ollama": "localhost:11434", "external_calls": 0}


@app.get("/api/health")
async def health():
    """Check Ollama connectivity."""
    try:
        r = await app.state.health_client.get("/api/tags")
        models = r.json().get("models", [])
        return {
            "status": "ok",
            "ollama": "connected",
            "available_models": [m["name"] for m in models],
        }
    except Exception as e:
        return {"status": "degraded", "ollama": "unreachable", "error": str(e)}
