from typing import Optional
from app.vector_store.chroma_client import chroma_client, VectorDocument


class SemanticRetriever:
    def __init__(self, embedding_pipeline=None):
        self._embedding_pipeline = embedding_pipeline

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        min_gem_score: Optional[float] = None,
    ) -> list[dict]:
        if self._embedding_pipeline is None:
            return []

        query_embedding = self._embedding_pipeline.encode(query)

        filter_meta = None
        if min_gem_score is not None:
            filter_meta = {"gem_score": {"$gte": min_gem_score}}

        docs = chroma_client.query(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_meta,
        )

        return [
            {
                "id": d.id,
                "text": d.text,
                "metadata": d.metadata,
            }
            for d in docs
        ]

    async def query_expand(self, query: str, target_lang: str = "vi") -> str:
        return query
