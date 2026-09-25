"""
RAG router — ChromaDB + nomic-embed-text embeddings.
Fully local vector search. No cloud calls.
"""
import json
import uuid
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from config import MODELS, OLLAMA_BASE_URL
from routers.network_monitor import record_call

router = APIRouter()

# Lazy-load ChromaDB and SentenceTransformer
_chroma_client = None
_collection = None
_embedder = None


def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        try:
            import chromadb
            # Resolve from this source file, not the process working directory.
            # Uvicorn, tests, and Docker launch from different directories.
            backend_dir = Path(__file__).resolve().parents[1]
            project_dir = backend_dir.parent
            candidates = [
                project_dir / "mrpl_chroma_db",  # development / seeded KB
                backend_dir / "mrpl_chroma_db",
                backend_dir / "chroma_db",
            ]
            db_path = next((path for path in candidates if path.exists()), candidates[-1])

            _chroma_client = chromadb.PersistentClient(path=str(db_path))
            existing_cols = [c.name for c in _chroma_client.list_collections()]
            if "mrpl_knowledge_base" in existing_cols:
                _collection = _chroma_client.get_collection(name="mrpl_knowledge_base")
            else:
                _collection = _chroma_client.get_or_create_collection(
                    name="mrpl_knowledge",
                    metadata={"description": "MRPL internal knowledge base"},
                )
        except Exception as e:
            raise HTTPException(503, f"ChromaDB unavailable: {e}")
    return _collection


async def embed_text(text: str, model_type: str = "nomic-embed-text") -> List[float]:
    """Get embeddings dynamically using either SentenceTransformer or Ollama."""
    global _embedder
    if model_type == "all-MiniLM-L6-v2":
        if _embedder is None:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        import asyncio
        loop = asyncio.get_event_loop()
        emb = await loop.run_in_executor(None, lambda: _embedder.encode(text).tolist())
        return emb
    else:
        record_call("ollama_local", f"embed: {text[:40]}")
        payload = {"model": MODELS["embed"]["tag"], "prompt": text}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{OLLAMA_BASE_URL}/api/embeddings", json=payload)
            return r.json().get("embedding", [])


class IngestRequest(BaseModel):
    texts: List[str]
    metadatas: Optional[List[dict]] = None
    ids: Optional[List[str]] = None


class QueryRequest(BaseModel):
    query: str
    n_results: int = 3
    with_llm_answer: bool = True


@router.post("/ingest")
async def ingest_documents(req: IngestRequest):
    """Ingest text chunks into ChromaDB with appropriate embeddings."""
    col = get_collection()
    ids = req.ids or [str(uuid.uuid4()) for _ in req.texts]
    metas = req.metadatas or [{"source": "manual"} for _ in req.texts]

    model_type = "nomic-embed-text"
    if col.name == "mrpl_knowledge_base":
        model_type = "all-MiniLM-L6-v2"

    embeddings = []
    for text in req.texts:
        emb = await embed_text(text, model_type)
        embeddings.append(emb)

    col.upsert(documents=req.texts, embeddings=embeddings, ids=ids, metadatas=metas)
    return {"ingested": len(req.texts), "external_calls": 0}


@router.post("/query")
async def query_knowledge(req: QueryRequest):
    """Semantic search + optional Phi-3.5 answer generation."""
    col = get_collection()
    
    model_type = "nomic-embed-text"
    if col.name == "mrpl_knowledge_base":
        model_type = "all-MiniLM-L6-v2"

    query_emb = await embed_text(req.query, model_type)

    results = col.query(
        query_embeddings=[query_emb],
        n_results=min(req.n_results, col.count() or 1),
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0] if results["documents"] else []
    dists = results["distances"][0] if results["distances"] else []

    context_str = "\n\n---\n\n".join(docs)
    llm_answer = ""

    if req.with_llm_answer and docs:
        record_call("ollama_local", f"rag answer: {req.query[:40]}")
        rag_prompt = (
            f"You are MRPL's internal knowledge assistant. "
            f"Answer the question using ONLY the following context.\n\n"
            f"CONTEXT:\n{context_str}\n\n"
            f"QUESTION: {req.query}\n\n"
            f"Answer concisely and cite relevant context."
        )
        payload = {
            "model": MODELS["reasoning"]["tag"],
            "prompt": rag_prompt,
            "stream": False,
            "options": {"num_ctx": 4096, "temperature": 0.3},
        }
        async with httpx.AsyncClient(timeout=None) as client:
            r = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            llm_answer = r.json().get("response", "")

    return {
        "query": req.query,
        "retrieved_chunks": [
            {"text": d, "distance": round(dist, 4), "metadata": m}
            for d, dist, m in zip(docs, dists, results["metadatas"][0] or [])
        ],
        "llm_answer": llm_answer,
        "model_used": MODELS["reasoning"]["display"],
        "external_calls": 0,
    }


@router.get("/stats")
async def kb_stats():
    try:
        col = get_collection()
        return {"document_count": col.count(), "status": "ok", "external_calls": 0}
    except Exception as e:
        return {"document_count": 0, "status": str(e)}


@router.post("/seed")
async def seed_knowledge_base():
    """Seed with sample MRPL knowledge for demo purposes."""
    sample_docs = [
        "MRPL CDU-1 crude distillation unit operates at 103 MMTPA capacity. Feed: Arabian Heavy crude. Key parameters: Atmospheric pressure 1.01 bar, top temperature 120°C, bottom temperature 360°C.",
        "Inspection procedure for heat exchangers at MRPL: Visual inspection quarterly, hydrostatic pressure test annually at 1.5x design pressure, NDT using UT thickness gauging every 6 months.",
        "MRPL emergency shutdown procedure (ESD): Trigger conditions include feed pump failure, high-high temperature alarm >380°C, or pressure relief valve lift. SIS initiates within 2 seconds.",
        "P&ID notation standards at MRPL: FIC = Flow Indicating Controller, PIC = Pressure Indicating Controller, TIC = Temperature Indicating Controller, LIC = Level Indicating Controller.",
        "Corrosion monitoring protocol: High-temperature sulfidation monitoring at CDU flash zone. Acceptable corrosion rate: <0.1 mm/year. Probe locations: 15 fixed + 8 portable points.",
        "MRPL safety standards reference: API 510 (pressure vessel inspection), API 570 (piping inspection), ASME B31.3 (process piping), IS 2825 (pressure vessel code).",
        "Heat exchanger LMTD calculation: LMTD = (ΔT1 - ΔT2) / ln(ΔT1/ΔT2) where ΔT1 and ΔT2 are temperature differences at each end. Correction factor F applies for multi-pass exchangers.",
        "CDU-2 feed preheat train: 7 heat exchangers in series (E-201 to E-207). Design duty: 45 MW. Crude inlet: 30°C, desalter outlet: 135°C, furnace inlet target: 245°C.",
    ]

    col = get_collection()
    ids = [f"seed_{i}" for i in range(len(sample_docs))]
    metas = [{"source": "mrpl_ops_manual", "seed": True} for _ in sample_docs]

    embeddings = []
    for text in sample_docs:
        emb = await embed_text(text)
        embeddings.append(emb)

    col.upsert(documents=sample_docs, embeddings=embeddings, ids=ids, metadatas=metas)
    return {"seeded": len(sample_docs), "external_calls": 0}
