import logging
from dataclasses import dataclass
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


@dataclass
class EmbeddingResult:
    text: str
    embedding: list[float]
    metadata: dict
    review_id: Optional[int] = None


class EmbeddingPipeline:
    def __init__(self, model_id: str = MODEL_ID, device: str = "cpu"):
        self.model_id = model_id
        self.device = device or settings.model_device
        self._model = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_id}")
            self._model = SentenceTransformer(
                self.model_id,
                cache_folder=settings.model_cache_dir,
                device=self.device if self.device == "cuda" else "cpu",
            )
            dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded. Dimension: {dim}")
        except Exception as e:
            logger.warning(f"Could not load sentence-transformers: {e}")

        if self._model is None:
            self._load_zero_shot()
        self._loaded = True

    def _load_zero_shot(self):
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            logger.info("Loading MiniLM via transformers for zero-shot embeddings...")
            self._hf_tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self._hf_model = AutoModel.from_pretrained(self.model_id)
            self._hf_model.eval()
        except Exception as e:
            logger.warning(f"Could not load MiniLM transformer: {e}")

    def encode(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM

        if self._model is not None:
            try:
                embedding = self._model.encode(text, normalize_embeddings=True)
                return embedding.tolist()
            except Exception as e:
                logger.warning(f"SentenceTransformer encode failed: {e}")

        if hasattr(self, "_hf_model") and self._hf_model is not None:
            return self._mean_pool_encode(text)

        return self._fallback_embed(text)

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if self._model is not None:
            try:
                embeddings = self._model.encode(
                    texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False
                )
                return [e.tolist() for e in embeddings]
            except Exception as e:
                logger.warning(f"Batch encode failed: {e}")
        return [self.encode(t) for t in texts]

    def _mean_pool_encode(self, text: str) -> list[float]:
        try:
            import torch
            encoded = self._hf_tokenizer(
                text, padding=True, truncation=True, max_length=512, return_tensors="pt"
            )
            with torch.no_grad():
                outputs = self._hf_model(**encoded)
                attention_mask = encoded["attention_mask"]
                token_embeddings = outputs.last_hidden_state
                input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                embedding = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
                    input_mask_expanded.sum(1), min=1e-9
                )
                norm = torch.norm(embedding, p=2, dim=1, keepdim=True)
                embedding = embedding / norm
            return embedding.squeeze().tolist()
        except Exception as e:
            logger.warning(f"Mean pool encode failed: {e}")
            return self._fallback_embed(text)

    def _fallback_embed(self, text: str) -> list[float]:
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(h[:4], "big")
        import random
        rng = random.Random(seed)
        return [rng.uniform(-0.1, 0.1) for _ in range(EMBEDDING_DIM)]

    def embed_reviews(self, reviews: list[dict]) -> list[EmbeddingResult]:
        results = []
        for r in reviews:
            body = r.get("body_text", "") or r.get("text", "")
            embedding = self.encode(body)
            results.append(EmbeddingResult(
                text=body,
                embedding=embedding,
                metadata={
                    "review_id": r.get("id"),
                    "restaurant_id": r.get("restaurant_id"),
                    "authenticity_score": r.get("authenticity_score"),
                    "sentiment": r.get("sentiment"),
                    "source": r.get("source"),
                    "timestamp": r.get("timestamp"),
                },
                review_id=r.get("id"),
            ))
        return results

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM
