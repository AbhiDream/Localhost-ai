# MRPL AI Workbench — PS 26117 (SIH 2026)

> **Self-hosted · Air-gapped · On-premises AI for Oil Refineries**  
> All inference runs locally via [Ollama](https://ollama.com). Zero cloud calls. Zero data leaves the premises.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MRPL Premises (Air-gapped)            │
│                                                          │
│  ┌──────────────┐   SSE Stream   ┌──────────────────┐   │
│  │ React + Vite │◄──────────────►│  FastAPI Backend  │   │
│  │  :5173       │                │  :8000            │   │
│  └──────────────┘                └────────┬─────────┘   │
│                                           │              │
│                         ┌─────────────────┼────────────┐ │
│                         │         Ollama  :11434        │ │
│                         │  ┌────────────────────────┐  │ │
│                         │  │ phi3.5      (reasoning) │  │ │
│                         │  │ qwen2.5-coder:3b (code) │  │ │
│                         │  │ moondream:1.8b (vision) │  │ │
│                         │  │ nomic-embed-text (RAG)  │  │ │
│                         │  └────────────────────────┘  │ │
│                         └───────────────────────────────┘ │
│                                                          │
│  ┌──────────────┐   ┌─────────────┐   ┌──────────────┐  │
│  │  ChromaDB    │   │   EasyOCR   │   │  python-docx │  │
│  │  (vectors)   │   │   (CPU)     │   │  openpyxl    │  │
│  └──────────────┘   └─────────────┘   └──────────────┘  │
└─────────────────────────────────────────────────────────┘
              ▲ NO outbound traffic ▲
```

## Model Router

| Prompt keywords         | Model routed to     | VRAM  |
|-------------------------|---------------------|-------|
| report, inspection, SOP | Phi-3.5 Mini        | 2.2 GB |
| python, code, LMTD, calc| Qwen2.5-Coder 3B    | 1.9 GB |
| image, P&ID, diagram    | Moondream 2         | 1.1 GB |
| (embeddings)            | nomic-embed-text    | CPU   |

Models are swapped one at a time — **total VRAM ≤ 4 GB**.

---

## Quick Start (Windows — Local Dev, No Docker)

### 1. Pull Models (one-time)
```powershell
ollama pull phi3.5
ollama pull qwen2.5-coder:3b
ollama pull moondream:1.8b
ollama pull nomic-embed-text
```

### 2. Launch
```powershell
# Double-click start.bat  OR:
.\start.bat
```

### 3. Open
- Workbench UI → http://localhost:5173  
- API Docs     → http://localhost:8000/docs

---

## Docker Deployment (Air-gapped)

```bash
# Build and run (internal bridge network)
docker compose up --build

# Belt-and-suspenders: block all egress at firewall
iptables -A OUTPUT -p tcp --dport 443 -j DROP
iptables -A OUTPUT -p tcp --dport 80  -j DROP
```

---

## Project Structure

```
sih/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Model routing config
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── outputs/             # Generated .docx / .py files
│   ├── uploads/             # Uploaded images for OCR
│   ├── chroma_db/           # ChromaDB vector store
│   └── routers/
│       ├── chat.py          # SSE streaming chat
│       ├── documents.py     # .docx / .py generation
│       ├── ocr.py           # EasyOCR + Moondream
│       ├── rag.py           # ChromaDB RAG
│       └── network_monitor.py
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── Header.jsx
│       │   ├── ModelBar.jsx
│       │   ├── Sidebar.jsx       # Prompt cards + RAG tab
│       │   ├── ChatPanel.jsx     # SSE streaming chat UI
│       │   └── NetworkMonitor.jsx # Live call auditing
│       ├── App.css
│       └── index.css
├── docker-compose.yml
├── start.bat                # Windows one-click launcher
└── start.sh                 # Linux/macOS launcher
```

---

## Sovereignty Proof

The **Network Monitor** panel shows a live call log. Every inference call is tagged:

- ✓ `ollama_local` — stays on-premises
- ✗ `external` — would indicate a breach (never happens)

**Forensic proof for evaluators:**
```bash
# Terminal 1: watch container stats
docker stats

# Terminal 2: capture outbound traffic
tcpdump -i any 'tcp port 443 or tcp port 80' -n
# → Should show zero packets during inference
```

---

## Features

| Feature | Implementation |
|---------|---------------|
| Streaming chat | FastAPI SSE → React EventSource |
| Model routing | Keyword-based router in `config.py` |
| Document generation | `python-docx` formatted .docx reports |
| Code generation | Qwen2.5-Coder → downloadable .py |
| RAG knowledge base | ChromaDB + nomic-embed-text |
| OCR | EasyOCR (CPU, zero VRAM) |
| P&ID analysis | Moondream vision model |
| Network monitoring | Live call auditing, sovereignty banner |
| Air-gap enforcement | Docker internal network + iptables |
