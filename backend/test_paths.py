import os
import chromadb

print("Current Working Directory:", os.getcwd())
print("../mrpl_chroma_db exists:", os.path.exists("../mrpl_chroma_db"))
print("mrpl_chroma_db exists:", os.path.exists("mrpl_chroma_db"))
print("chroma_db exists:", os.path.exists("chroma_db"))

db_path = "chroma_db"
if os.path.exists("../mrpl_chroma_db"):
    db_path = "../mrpl_chroma_db"
elif os.path.exists("mrpl_chroma_db"):
    db_path = "mrpl_chroma_db"

print("Selected DB Path:", db_path)
client = chromadb.PersistentClient(path=db_path)
print("Collections found in selected DB Path:")
for col in client.list_collections():
    print(f"- {col.name} ({col.count()} items)")
