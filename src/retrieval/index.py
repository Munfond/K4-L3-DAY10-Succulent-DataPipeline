from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd

from core.config import Settings
from core.utils import read_json, safe_slug, write_json
from retrieval.embeddings import MiniLMEmbeddings


@dataclass(frozen=True)
class SearchResult:
    paper_id: str
    title: str
    score: float
    content: str
    metadata: dict[str, Any]


class LocalEmbeddingIndex:
    _REQUIRED_COLUMNS = frozenset(
        {
            "paper_id",
            "title",
            "summary",
            "authors_joined",
            "categories_joined",
            "published",
            "abs_url",
            "pdf_url",
            "text_for_embedding",
        }
    )

    def __init__(
        self,
        settings: Settings,
        collection_name: str | None = None,
        documents: list[dict[str, Any]] | None = None,
        persist_path: Path | None = None,
    ):
        self.settings = settings
        self.collection_name = collection_name or settings.baseline_collection_name
        self.persist_path = persist_path or settings.paths.chroma_dir
        self.embedding_backend = "chroma"
        self.embedding_model = MiniLMEmbeddings(settings.embedding_model)
        self.client = chromadb.PersistentClient(path=str(self.persist_path))
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except Exception:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                configuration={"hnsw": {"space": "cosine"}},
            )

        if documents is None:
            manifest_candidates = [
                settings.paths.embeddings_json,
                settings.paths.corrupted_embeddings_json,
                settings.paths.repaired_embeddings_json,
            ]
            loaded_docs: list[dict[str, Any]] = []
            for candidate in manifest_candidates:
                if candidate.exists():
                    try:
                        data = read_json(candidate)
                        if data.get("collection_name") == self.collection_name:
                            loaded_docs = data.get("documents", [])
                            break
                    except Exception:
                        pass
            self.documents = loaded_docs
        else:
            self.documents = documents

        self.documents_by_paper_id = {
            str(document["paper_id"]).strip().casefold(): document
            for document in self.documents
            if isinstance(document, dict) and "paper_id" in document
        }
        self.documents_by_title = {
            str(document["title"]).strip().casefold(): document
            for document in self.documents
            if isinstance(document, dict) and "title" in document
        }

    @staticmethod
    def _build_documents(df: pd.DataFrame) -> list[dict[str, Any]]:
        if df.empty:
            raise ValueError("the index requires at least one document.")
        missing_columns = sorted(LocalEmbeddingIndex._REQUIRED_COLUMNS.difference(df.columns))
        if missing_columns:
            raise ValueError(f"missing required columns: {', '.join(missing_columns)}")

        records = df.to_dict(orient="records")
        documents: list[dict[str, Any]] = []
        for index, row in enumerate(records):
            paper_id = str(row["paper_id"]).strip()
            title = str(row["title"]).strip()
            content = str(row["text_for_embedding"]).strip()
            if not paper_id or not title or not content:
                raise ValueError(f"row {index} has an empty paper_id, title, or text_for_embedding.")
            documents.append(
                {
                    "record_id": f"{paper_id}::{index}",
                    "paper_id": paper_id,
                    "title": title,
                    "content": content,
                    "metadata": {
                        "paper_id": paper_id,
                        "title": title,
                        "published": str(row["published"]),
                        "authors_joined": str(row["authors_joined"]),
                        "categories_joined": str(row["categories_joined"]),
                        "summary": str(row["summary"]),
                        "abs_url": str(row["abs_url"]),
                        "pdf_url": str(row["pdf_url"]),
                    },
                }
            )
        return documents

    @staticmethod
    def _derive_collection_name(settings: Settings, embeddings_output_path: Path | None) -> str:
        if embeddings_output_path is None:
            return settings.baseline_collection_name

        name_map = {
            settings.paths.embeddings_json.resolve(): settings.baseline_collection_name,
            settings.paths.corrupted_embeddings_json.resolve(): settings.corrupted_collection_name,
            settings.paths.repaired_embeddings_json.resolve(): settings.repaired_collection_name,
        }
        resolved_path = embeddings_output_path.resolve()
        if resolved_path in name_map:
            return name_map[resolved_path]
        return safe_slug(embeddings_output_path.stem)

    @classmethod
    def build(
        cls,
        df: pd.DataFrame,
        settings: Settings,
        embeddings_output_path: Path | None = None,
    ) -> "LocalEmbeddingIndex":
        collection_name = cls._derive_collection_name(settings, embeddings_output_path)
        documents = cls._build_documents(df)
        persist_path = settings.paths.chroma_dir
        persist_path.mkdir(parents=True, exist_ok=True)

        embedding_model = MiniLMEmbeddings(settings.embedding_model)
        client = chromadb.PersistentClient(path=str(persist_path))
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = client.create_collection(
            name=collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )
        embeddings = embedding_model.embed_documents([document["content"] for document in documents])
        collection.add(
            ids=[document["record_id"] for document in documents],
            embeddings=embeddings,
            documents=[document["content"] for document in documents],
            metadatas=[document["metadata"] for document in documents],
        )

        manifest_path = embeddings_output_path or settings.paths.embeddings_json
        write_json(
            manifest_path,
            {
                "backend": "chroma",
                "embedding_model": settings.embedding_model,
                "persist_path": str(persist_path),
                "collection_name": collection_name,
                "documents": documents,
            },
        )
        return cls(
            settings=settings,
            collection_name=collection_name,
            documents=documents,
            persist_path=persist_path,
        )

    @classmethod
    def load(cls, settings: Settings, embeddings_path: Path | None = None) -> "LocalEmbeddingIndex":
        payload = read_json(embeddings_path or settings.paths.embeddings_json)
        return cls(
            settings=settings,
            collection_name=payload["collection_name"],
            documents=payload["documents"],
            persist_path=Path(payload["persist_path"]),
        )

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        requested_top_k = self.settings.top_k if top_k is None else top_k
        if isinstance(requested_top_k, bool) or not isinstance(requested_top_k, int) or requested_top_k <= 0:
            raise ValueError("top_k must be a positive integer.")
        document_count = self.collection.count()
        if document_count == 0:
            return []

        query_embedding = self.embedding_model.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(requested_top_k, document_count),
            include=["documents", "metadatas", "distances"],
        )
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        scored: list[SearchResult] = []
        for record_id, content, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            if not record_id or not metadata or not content:
                continue
            score = max(0.0, min(1.0, 1.0 - float(distance or 0.0)))
            scored.append(
                SearchResult(
                    paper_id=str(metadata["paper_id"]),
                    title=str(metadata["title"]),
                    score=score,
                    content=str(content),
                    metadata=dict(metadata),
                )
            )
        return scored

    def lookup(self, value: str) -> dict[str, Any] | None:
        if not isinstance(value, str):
            return None
        needle = value.strip().casefold()
        if needle in self.documents_by_paper_id:
            return self.documents_by_paper_id[needle]
        if needle in self.documents_by_title:
            return self.documents_by_title[needle]
        return None

    def semantic_search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        return self.search(query=query, top_k=top_k)

    def build_from_clean(self, clean_path: Path | str | None = None) -> "LocalEmbeddingIndex":
        """Build the embedding index from clean papers dataset."""
        target_path = Path(clean_path) if clean_path else self.settings.paths.clean_json
        if not target_path.exists():
            target_path = self.settings.paths.clean_csv
        if not target_path.exists():
            raise FileNotFoundError(f"Clean papers file not found at {target_path}")

        if str(target_path).endswith(".csv"):
            df = pd.read_csv(target_path)
        else:
            df = pd.read_json(target_path)

        self.persist_path.mkdir(parents=True, exist_ok=True)
        documents = self._build_documents(df)
        self.documents = documents
        self.documents_by_paper_id = {
            str(doc["paper_id"]).strip().casefold(): doc for doc in documents
        }
        self.documents_by_title = {
            str(doc["title"]).strip().casefold(): doc for doc in documents
        }

        try:
            self.client.delete_collection(name=self.collection_name)
        except Exception:
            pass
        self.collection = self.client.create_collection(
            name=self.collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )
        embeddings = self.embedding_model.embed_documents([doc["content"] for doc in documents])
        self.collection.add(
            ids=[doc["record_id"] for doc in documents],
            embeddings=embeddings,
            documents=[doc["content"] for doc in documents],
            metadatas=[doc["metadata"] for doc in documents],
        )

        manifest_path = self.settings.paths.embeddings_json
        write_json(
            manifest_path,
            {
                "backend": "chroma",
                "embedding_model": self.settings.embedding_model,
                "persist_path": str(self.persist_path),
                "collection_name": self.collection_name,
                "documents": documents,
            },
        )
        return self

