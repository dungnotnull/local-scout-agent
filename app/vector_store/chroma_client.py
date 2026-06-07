import uuid
from typing import Optional
from dataclasses import dataclass
from app.config import settings


@dataclass
class VectorDocument:
    id: str
    embedding: list[float]
    metadata: dict
    text: str


class ChromaClient:
    def __init__(self, persist_path: str = None):
        self.persist_path = persist_path or settings.chroma_db_path
        self._client = None
        self._collection = None

    def initialize(self):
        import chromadb
        self._client = chromadb.PersistentClient(path=self.persist_path)
        self._collection = self._client.get_or_create_collection(
            name="restaurant_reviews",
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, documents: list[VectorDocument]):
        if not self._collection:
            self.initialize()
        ids = [d.id or str(uuid.uuid4()) for d in documents]
        embeddings = [d.embedding for d in documents]
        metadatas = [d.metadata for d in documents]
        texts = [d.text for d in documents]
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts,
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_metadata: Optional[dict] = None,
    ) -> list[VectorDocument]:
        if not self._collection:
            self.initialize()
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata,
        )
        docs = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                docs.append(VectorDocument(
                    id=doc_id,
                    embedding=results["embeddings"][0][i] if results.get("embeddings") and results["embeddings"][0] else [],
                    metadata=results["metadatas"][0][i] if results.get("metadatas") else {},
                    text=results["documents"][0][i] if results.get("documents") else "",
                ))
        return docs

    def delete_by_restaurant(self, restaurant_id: int):
        if not self._collection:
            self.initialize()
        self._collection.delete(where={"restaurant_id": restaurant_id})

    def count(self) -> int:
        if not self._collection:
            self.initialize()
        return self._collection.count()


chroma_client = ChromaClient()
