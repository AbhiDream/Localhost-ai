import chromadb
import pdfplumber
import uuid
import os
from sentence_transformers import SentenceTransformer

# Init ChromaDB
client = chromadb.PersistentClient(path="./mrpl_chroma_db")
collection = client.get_or_create_collection(
    name="mrpl_knowledge_base",
    metadata={"hnsw:space": "cosine"}
)

# Embedding model (runs fully offline after first download)
print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
print("Model loaded successfully.")

def ingest_pdf(pdf_path, source_name, document_title):
    chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text or len(text.strip()) < 50:
                continue
            # Split into ~500 char chunks with 50 char overlap
            words = text.split()
            for i in range(0, len(words), 80):
                chunk = " ".join(words[i:i+90])
                if len(chunk) > 100:
                    chunks.append({
                        "text": chunk,
                        "source": source_name,
                        "title": document_title,
                        "page": page_num + 1
                    })
    
    if not chunks:
        return 0
    
    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts).tolist()
    
    collection.add(
        ids=[str(uuid.uuid4()) for _ in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{
            "source": c["source"],
            "title": c["title"],
            "page": str(c["page"])
        } for c in chunks]
    )
    return len(chunks)

# Run for every downloaded PDF
pdf_folder = "./downloaded_docs"
for filename in os.listdir(pdf_folder):
    if filename.endswith(".pdf"):
        path = os.path.join(pdf_folder, filename)
        name = filename.replace(".pdf", "")
        # Create human-readable title from name
        title = name.replace("_", " ").title()
        count = ingest_pdf(path, source_name=name, document_title=title)
        print(f"Ingested {count} chunks from {filename}")

print(f"Total docs in KB: {collection.count()}")
