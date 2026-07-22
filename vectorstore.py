import os
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

CHROMA_PATH = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
_client = None
_collection = None

def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    _client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = DefaultEmbeddingFunction()
    _collection = _client.get_or_create_collection("rag_docs", embedding_function=ef)
    return _collection

def add_document(filename: str, chunks: list[str]) -> int:
    col = _get_collection()
    existing = col.get(where={"source": filename})
    if existing["ids"]:
        return len(existing["ids"])  # already indexed, skip
    start = col.count()
    col.add(
        documents=chunks,
        ids=[f"chunk_{start + i}" for i in range(len(chunks))],
        metadatas=[{"source": filename} for _ in chunks],
    )
    return len(chunks)

def query(question: str, n: int = 4) -> list[dict]:
    col = _get_collection()
    total = col.count()
    if total == 0:
        return []
    results = col.query(query_texts=[question], n_results=min(n, total))
    return [
        {"doc": m["source"], "text": d}
        for m, d in zip(results["metadatas"][0], results["documents"][0])
    ]

def get_stats() -> dict:
    col = _get_collection()
    total = col.count()
    sources = set()
    if total > 0:
        all_meta = col.get(include=["metadatas"])["metadatas"]
        sources = {m["source"] for m in all_meta}
    return {"total_chunks": total, "documents": sorted(sources)}
