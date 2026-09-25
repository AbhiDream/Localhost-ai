"""
Central configuration for the MRPL AI Workbench.
All inference is routed to Ollama running on localhost.
"""

OLLAMA_BASE_URL = "http://localhost:11434"

# Model routing table
MODELS = {
    "reasoning": {
        "tag": "phi3.5:latest",
        "display": "Phi-3.5 Mini",
        "vram_gb": 2.2,
        "role": "Reasoning, reports, SOPs, approval notes",
        "color": "#6366f1",
    },
    "code": {
        "tag": "qwen2.5-coder:3b",
        "display": "Qwen2.5-Coder 3B",
        "vram_gb": 1.9,
        "role": "Code, calculations, engineering scripts",
        "color": "#10b981",
    },
    "vision": {
        "tag": "llava-phi3:latest",
        "display": "Llava-Phi3",
        "vram_gb": 2.9,
        "role": "Vision, P&ID diagram analysis, equipment photos",
        "color": "#f59e0b",
    },
    "ocr": {
        "tag": "easyocr",
        "display": "EasyOCR (CPU)",
        "vram_gb": 0.0,
        "role": "Scanned documents, text extraction, inspection reports",
        "color": "#ec4899",
    },
    "embed": {
        "tag": "nomic-embed-text:latest",
        "display": "Nomic Embed",
        "vram_gb": 0.0,
        "role": "Embeddings for RAG (CPU only)",
        "color": "#8b5cf6",
    },
}

# Router keyword map — simple intent classifier
ROUTING_KEYWORDS = {
    "code": [
        "python", "script", "function", "code", "calculate", "lmtd", "formula",
        "algorithm", "compute", "math", "equation", "program", "def ", "import ",
    ],
    "vision": [
        "image", "diagram", "p&id", "pid", "photo", "picture", "scan",
        "drawing", "schematic", "blueprint", "figure", "chart",
    ],
    "reasoning": [
        "report", "inspection", "approval", "sop", "procedure", "note", "summary",
        "analysis", "recommendation", "explain", "describe", "what is", "how to",
        "lookup", "find", "search", "regulation", "standard",
    ],
}

# Task classification for the agentic pipeline
TASK_KEYWORDS = {
    "document": [
        "report", "approval note", "draft", "inspection report",
        "sop", "standard operating procedure", "document",
        "word file", "docx", "generate a",
        "presentation", "pptx", "ppt", "slides",
        "spreadsheet", "excel", "xlsx",
    ],
    "code": [
        "code", "python", "script", "calculate", "lmtd", "computation",
        "algorithm", "function", "engineering calculation", "formula",
        "program", "compute", "def ", "import ",
    ],
    "knowledge": [
        "what does", "according to", "oisd", "api 5", "asme", "is 2825",
        "regulation", "standard", "procedure for", "guidelines",
        "knowledge base", "look up", "find in", "search for",
        "what is the", "how to", "tell me about", "handbook", "manual",
    ],
    "vision": [
        "this image", "this diagram", "this photo", "attached image",
        "p&id", "pid diagram", "analyze image", "what do you see",
        "scanned", "handwritten", "drawing",
    ],
}


def route_model(prompt: str, force_model: str | None = None) -> str:
    """
    Determine which model to use based on prompt keywords.
    Returns the model key ('reasoning' | 'code' | 'vision').
    """
    if force_model and force_model in MODELS:
        return force_model

    prompt_lower = prompt.lower()
    scores = {k: 0 for k in ROUTING_KEYWORDS}

    for model_key, keywords in ROUTING_KEYWORDS.items():
        for kw in keywords:
            if kw in prompt_lower:
                scores[model_key] += 1

    # Default to reasoning if no strong signal
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "reasoning"


def classify_task(prompt: str, has_image: bool = False, has_pdf: bool = False) -> dict:
    """
    Classify user request into task type and determine which agent phases to run.
    Returns: {"task_type": str, "phases": list[str], "model_key": str}
    """
    prompt_lower = prompt.lower()
    scores = {k: 0 for k in TASK_KEYWORDS}

    for task, keywords in TASK_KEYWORDS.items():
        for kw in keywords:
            if kw in prompt_lower:
                scores[task] += 2 if len(kw) > 10 else 1

    best_task = max(scores, key=scores.get)
    if scores[best_task] == 0:
        best_task = "general"

    # Override if file attached
    if has_image:
        best_task = "vision"
    if has_pdf and best_task == "general":
        best_task = "knowledge"

    # Determine phases and model for each task type
    phase_map = {
        "document":  {"phases": ["reason", "artifact"], "model_key": "reasoning"},
        # Demo-safe mode: generate code locally but do not execute it. This
        # avoids launching a subprocess and keeps the sovereignty dashboard
        # focused on inference and knowledge retrieval only.
        "code":      {"phases": ["reason"], "model_key": "code"},
        "knowledge": {"phases": ["retrieve", "reason"],            "model_key": "reasoning"},
        "vision":    {"phases": ["extract", "reason"],             "model_key": "vision"},
        "general":   {"phases": ["reason"],                        "model_key": "reasoning"},
    }

    # Copy the list: phase additions below must not mutate phase_map across requests.
    selected = phase_map.get(best_task, phase_map["general"])
    result = {"phases": list(selected["phases"]), "model_key": selected["model_key"]}
    result["task_type"] = best_task

    # Dynamically inject RAG only if knowledge keywords are present (saves 30s model swap time)
    if scores["knowledge"] > 0 and "retrieve" not in result["phases"]:
        result["phases"].insert(0, "retrieve")

    # If file attached, prepend extract phase
    if (has_image or has_pdf) and "extract" not in result["phases"]:
        result["phases"].insert(0, "extract")

    return result
