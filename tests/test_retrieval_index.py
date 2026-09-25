from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.config import load_settings
from core.utils import read_json
from retrieval import embeddings
from retrieval.index import LocalEmbeddingIndex


class FakeSentenceTransformer:
    instances: list["FakeSentenceTransformer"] = []

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.encode_calls: list[tuple[list[str], bool]] = []
        self.__class__.instances.append(self)

    def encode(self, texts, normalize_embeddings: bool = False):
        values = [str(text) for text in texts]
        self.encode_calls.append((values, normalize_embeddings))
        return np.asarray(
            [[float(len(text) + 1), float(index + 1), 1.0] for index, text in enumerate(values)],
            dtype=float,
        )


@pytest.fixture
def fake_embedding_model(monkeypatch):
    FakeSentenceTransformer.instances.clear()
    monkeypatch.setattr(embeddings, "SentenceTransformer", FakeSentenceTransformer)
    embeddings._load_model.cache_clear()
    yield
    embeddings._load_model.cache_clear()


@pytest.fixture
def settings(tmp_path):
    return load_settings(project_dir=tmp_path)


@pytest.fixture
def papers() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "paper_id": "doi-1",
                "title": "Agentic retrieval",
                "summary": "Retrieval grounded generation improves factual answers.",
                "authors_joined": "Alice A, Bob B",
                "categories_joined": "Artificial Intelligence, Information Retrieval",
                "published": "2026-01-02",
                "abs_url": "https://example.test/doi-1",
                "pdf_url": "https://example.test/doi-1.pdf",
                "text_for_embedding": "Title: Agentic retrieval\nSummary: Retrieval grounded generation improves factual answers.",
            },
            {
                "paper_id": "doi-2",
                "title": "Fresh vector stores",
                "summary": "Fresh indexes reduce stale retrieval results.",
                "authors_joined": "Carol C",
                "categories_joined": "Data Systems",
                "published": "2026-01-03",
                "abs_url": "https://example.test/doi-2",
                "pdf_url": "https://example.test/doi-2.pdf",
                "text_for_embedding": "Title: Fresh vector stores\nSummary: Fresh indexes reduce stale retrieval results.",
            },
        ]
    )


def test_embedding_wrapper_validates_model_name_and_reuses_model(fake_embedding_model):
    first = embeddings.MiniLMEmbeddings("fake-model")
    second = embeddings.MiniLMEmbeddings("fake-model")

    assert first.model is second.model
    assert len(FakeSentenceTransformer.instances) == 1
    assert first.embed_documents(["one", "two"]).__class__ is list
    assert first.embed_query("query").__class__ is list
    assert all(call[1] for call in FakeSentenceTransformer.instances[0].encode_calls)

    with pytest.raises(ValueError, match="model_name"):
        embeddings.MiniLMEmbeddings("  ")

    with pytest.raises(ValueError, match="query"):
        first.embed_query("  ")


def test_build_rejects_empty_dataframe(settings, fake_embedding_model):
    with pytest.raises(ValueError, match="at least one document"):
        LocalEmbeddingIndex.build(pd.DataFrame(), settings, settings.paths.embeddings_json)


def test_build_rejects_missing_required_columns(settings, fake_embedding_model):
    with pytest.raises(ValueError, match="missing required columns"):
        LocalEmbeddingIndex.build(
            pd.DataFrame([{"paper_id": "doi-1", "title": "Only a title"}]),
            settings,
            settings.paths.embeddings_json,
        )


def test_build_search_and_load_preserve_manifest_and_metadata(settings, papers, fake_embedding_model):
    index = LocalEmbeddingIndex.build(papers, settings, settings.paths.embeddings_json)

    assert index.collection_name == settings.baseline_collection_name
    assert index.collection.count() == 2

    results = index.search("retrieval", top_k=1)
    assert len(results) == 1
    assert results[0].paper_id in {"doi-1", "doi-2"}
    assert results[0].content.startswith("Title:")
    assert results[0].metadata["authors_joined"]
    assert 0.0 <= results[0].score <= 1.0

    manifest = read_json(settings.paths.embeddings_json)
    assert manifest["embedding_model"] == settings.embedding_model
    assert manifest["collection_name"] == settings.baseline_collection_name
    assert len(manifest["documents"]) == 2

    loaded = LocalEmbeddingIndex.load(settings)
    assert loaded.collection_name == index.collection_name
    assert loaded.lookup(" DOI-1 ")["title"] == "Agentic retrieval"
    assert loaded.lookup("Fresh vector stores")["paper_id"] == "doi-2"


def test_build_uses_separate_collections_and_rebuild_is_idempotent(settings, papers, fake_embedding_model):
    LocalEmbeddingIndex.build(papers, settings, settings.paths.embeddings_json)
    corrupted = papers.iloc[:1].copy()
    LocalEmbeddingIndex.build(corrupted, settings, settings.paths.corrupted_embeddings_json)
    LocalEmbeddingIndex.build(papers, settings, settings.paths.repaired_embeddings_json)

    assert LocalEmbeddingIndex.load(settings, settings.paths.embeddings_json).collection.count() == 2
    assert LocalEmbeddingIndex.load(settings, settings.paths.corrupted_embeddings_json).collection.count() == 1
    assert LocalEmbeddingIndex.load(settings, settings.paths.repaired_embeddings_json).collection.count() == 2

    LocalEmbeddingIndex.build(corrupted, settings, settings.paths.embeddings_json)
    rebuilt = LocalEmbeddingIndex.load(settings, settings.paths.embeddings_json)
    assert rebuilt.collection.count() == 1


def test_search_rejects_non_positive_top_k(settings, papers, fake_embedding_model):
    index = LocalEmbeddingIndex.build(papers, settings, settings.paths.embeddings_json)

    with pytest.raises(ValueError, match="top_k"):
        index.search("retrieval", top_k=0)
