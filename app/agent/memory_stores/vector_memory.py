from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any


CHROMA_PATH = Path("data/chroma")
COLLECTION_NAME = "nexusti_knowledge"
EMBEDDING_DIMENSIONS = 128


class HashEmbeddingFunction:
    def __call__(self, input: list[str]) -> list[list[float]]:  # Chroma expects this argument name.
        return [_embed(text) for text in input]


class VectorMemoryStore:
    def __init__(self) -> None:
        self.provider = "chroma"
        self.available = importlib.util.find_spec("chromadb") is not None
        self.enabled = self.available
        self._client = None
        self._collection = None

    def status(self) -> dict:
        if not self.available:
            return {
                "enabled": False,
                "provider": "sqlite-fts5",
                "vector_provider": "chroma",
                "vector_available": False,
                "message": "Chroma nao esta instalado; RAG esta usando SQLite FTS/keyword fallback.",
            }
        try:
            collection = self.collection()
            count = collection.count()
        except Exception as exc:
            return {
                "enabled": False,
                "provider": "sqlite-fts5",
                "vector_provider": "chroma",
                "vector_available": True,
                "message": f"Chroma instalado, mas indisponivel: {exc}",
            }
        return {
            "enabled": True,
            "provider": "chroma",
            "vector_provider": "chroma",
            "vector_available": True,
            "documents": count,
            "path": str(CHROMA_PATH),
            "message": "Chroma PersistentClient ativo para RAG local.",
        }

    def collection(self):
        if not self.available:
            raise RuntimeError("Chroma nao instalado.")
        if self._collection is None:
            import chromadb

            CHROMA_PATH.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=HashEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def index(self, items: list[dict[str, Any]]) -> None:
        if not self.available or not items:
            return
        collection = self.collection()
        existing = set(collection.get(include=[])["ids"])
        ids = []
        documents = []
        metadatas = []
        for item in items:
            item_id = str(item["id"])
            if item_id in existing:
                continue
            ids.append(item_id)
            documents.append(item["content"])
            metadatas.append({key: str(value) for key, value in item.get("metadata", {}).items()})
        if ids:
            collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def search(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        if not self.available:
            return []
        collection = self.collection()
        if collection.count() <= 0:
            return []
        result = collection.query(query_texts=[query], n_results=limit, include=["documents", "metadatas", "distances"])
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        output = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = float(distances[index]) if index < len(distances) else 1.0
            output.append(
                {
                    "document_id": metadata.get("document_id", ""),
                    "title": metadata.get("title", "Documento Chroma"),
                    "category": metadata.get("category", "general"),
                    "content": document,
                    "tags": metadata.get("tags", ""),
                    "source": metadata.get("source", "chroma"),
                    "score": round(max(0.0, 1.0 - distance), 4),
                    "backend": "chroma",
                }
            )
        return output


def _embed(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = text.lower().split()
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
        index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / norm for value in vector]
