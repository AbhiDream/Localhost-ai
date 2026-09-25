#!/usr/bin/env bash
# ============================================================
# MRPL AI Workbench — Local Dev Startup Script (non-Docker)
# Requires: Python 3.11+, Node 18+, Ollama running on :11434
# ============================================================
set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   MRPL AI Workbench  ·  PS 26117  ·  SIH 2026   ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Check Ollama ──────────────────────────────────────────
echo "▶ Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "  ⚠  Ollama not running. Start it with: ollama serve"
  echo "  Then pull models:"
  echo "    ollama pull phi3.5"
  echo "    ollama pull qwen2.5-coder:3b"
  echo "    ollama pull moondream:1.8b"
  echo "    ollama pull nomic-embed-text"
  exit 1
fi
echo "  ✓ Ollama is up"

# ── 2. Backend ───────────────────────────────────────────────
echo ""
echo "▶ Starting FastAPI backend on :8000..."
cd backend
if [ ! -d ".venv" ]; then
  echo "  Creating virtualenv..."
  python -m venv .venv
fi
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -q -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "  ✓ Backend PID $BACKEND_PID"
cd ..

# ── 3. Frontend ──────────────────────────────────────────────
echo ""
echo "▶ Starting React frontend on :5173..."
cd frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
echo "  ✓ Frontend PID $FRONTEND_PID"
cd ..

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Workbench ready at  http://localhost:5173       ║"
echo "║  API docs at         http://localhost:8000/docs  ║"
echo "║  Press Ctrl+C to stop all services               ║"
echo "╚══════════════════════════════════════════════════╝"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
