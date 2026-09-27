import os
import glob
import pdfplumber
import csv
import asyncio
from pathlib import Path
from routers.rag import get_collection, embed_text

def chunk_text(text, chunk_size=1000, overlap=200):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

async def ingest_directory():
    kb_path = Path(r"C:\Users\adity\Desktop\sih\RAG\knowledge-base")
    if not kb_path.exists():
        print(f"Error: {kb_path} does not exist")
        return

    col = get_collection()
    
    # Determine model type for embeddings
    model_type = "nomic-embed-text"
    if col.name == "mrpl_knowledge_base":
        model_type = "all-MiniLM-L6-v2"
        
    print(f"Using collection: {col.name}")
    print(f"Using model: {model_type}")

    pdf_files = list(kb_path.rglob("*.pdf"))
    csv_files = list(kb_path.rglob("*.csv"))
    
    all_files = pdf_files + csv_files
    print(f"Found {len(all_files)} files to process.")

    total_chunks = 0
    for file_path in all_files:
        try:
            print(f"Processing {file_path.name}...")
            text = ""
            if file_path.suffix.lower() == '.pdf':
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            elif file_path.suffix.lower() == '.csv':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        text += " ".join(row) + "\n"
            
            if not text.strip():
                print(f"Skipping {file_path.name} - no text extracted")
                continue
                
            chunks = chunk_text(text)
            
            # Batch process chunks for this file
            batch_size = 5
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                ids = [f"{file_path.name}_{i+j}" for j in range(len(batch_chunks))]
                metas = [{"source": file_path.name, "path": str(file_path)} for _ in batch_chunks]
                
                embeddings = []
                for chunk in batch_chunks:
                    emb = await embed_text(chunk, model_type)
                    embeddings.append(emb)
                    
                col.upsert(documents=batch_chunks, embeddings=embeddings, ids=ids, metadatas=metas)
                total_chunks += len(batch_chunks)
                
            print(f"Ingested {len(chunks)} chunks from {file_path.name}")
        except Exception as e:
            print(f"Failed to process {file_path.name}: {e}")

    print(f"Successfully ingested {total_chunks} total chunks.")

if __name__ == "__main__":
    asyncio.run(ingest_directory())
