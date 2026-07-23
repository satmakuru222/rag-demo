import os
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

CHROMA_PATH = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
_client = None
_collections: dict = {}

def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client

def _get_collection(notebook_id: int):
    global _collections
    if notebook_id not in _collections:
        client = _get_client()
        ef = DefaultEmbeddingFunction()
        _collections[notebook_id] = client.get_or_create_collection(
            f"notebook_{notebook_id}", embedding_function=ef
        )
    return _collections[notebook_id]

def add_document(notebook_id: int, filename: str, chunks: list[str]) -> int:
    col = _get_collection(notebook_id)
    existing = col.get(where={"source": filename})
    if existing["ids"]:
        return len(existing["ids"])
    start = col.count()
    col.add(
        documents=chunks,
        ids=[f"nb{notebook_id}_chunk_{start + i}" for i in range(len(chunks))],
        metadatas=[{"source": filename} for _ in chunks],
    )
    return len(chunks)

def delete_document(notebook_id: int, filename: str):
    col = _get_collection(notebook_id)
    existing = col.get(where={"source": filename})
    if existing["ids"]:
        col.delete(ids=existing["ids"])

def delete_notebook_collection(notebook_id: int):
    client = _get_client()
    try:
        client.delete_collection(f"notebook_{notebook_id}")
        _collections.pop(notebook_id, None)
    except Exception:
        pass

def query(notebook_id: int, question: str, n: int = 4) -> list[dict]:
    col = _get_collection(notebook_id)
    total = col.count()
    if total == 0:
        return []
    results = col.query(query_texts=[question], n_results=min(n, total))
    return [
        {"doc": m["source"], "text": d}
        for m, d in zip(results["metadatas"][0], results["documents"][0])
    ]

def get_stats(notebook_id: int) -> dict:
    col = _get_collection(notebook_id)
    total = col.count()
    sources = set()
    if total > 0:
        all_meta = col.get(include=["metadatas"])["metadatas"]
        sources = {m["source"] for m in all_meta}
    return {"total_chunks": total, "documents": sorted(sources)}
