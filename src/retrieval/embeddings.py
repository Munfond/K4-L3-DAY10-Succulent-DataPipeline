from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=4)
def _load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


class MiniLMEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        normalized_model_name = model_name.strip()
        if not normalized_model_name:
            raise ValueError("model_name must not be empty.")
        self.model_name = normalized_model_name
        self.model = _load_model(normalized_model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("document texts must be non-empty strings.")
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("query must be a non-empty string.")
        embedding = self.model.encode([text], normalize_embeddings=True)
        return embedding[0].tolist()
