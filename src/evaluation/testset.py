from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, read_json, write_json


class TestSet(list):
    """Wrapper around test set samples list providing .samples attribute."""

    def __init__(self, samples: list[dict[str, Any]] | None = None):
        super().__init__(samples or [])

    @property
    def samples(self) -> list[dict[str, Any]]:
        return list(self)


def build_test_set(df: pd.DataFrame, output_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Build a deterministic 10-question benchmark from cleaned papers."""
    required_columns = {"paper_id", "title", "summary", "authors_joined", "published", "categories_joined"}
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Cannot build test set; missing columns: {', '.join(missing_columns)}")
    if len(df) < 4:
        raise ValueError("At least four cleaned papers are required to build a diverse test set.")

    papers = df.sort_values("paper_id", kind="stable").reset_index(drop=True)
    question_types = ["summary", "authors", "date", "categories", "summary", "authors", "date", "categories", "summary", "authors"]
    test_set: list[dict[str, Any]] = []

    for index, question_type in enumerate(question_types):
        paper = papers.iloc[index % len(papers)]
        title = normalize_whitespace(str(paper["title"]))
        paper_id = str(paper["paper_id"])
        values = {
            "summary": (
                f"What is the main finding of the paper '{title}'?",
                first_sentence(str(paper["summary"])),
            ),
            "authors": (
                f"Who authored the paper '{title}'?",
                normalize_whitespace(str(paper["authors_joined"])),
            ),
            "date": (
                f"When was the paper '{title}' published?",
                str(paper["published"]),
            ),
            "categories": (
                f"Which research categories are assigned to '{title}'?",
                normalize_whitespace(str(paper["categories_joined"])),
            ),
        }
        question, ground_truth = values[question_type]
        test_set.append(
            {
                "id": f"eval_{index + 1:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    if output_path is not None:
        write_json(Path(output_path), test_set)
    return test_set


def load_or_create_test_set(df: pd.DataFrame, output_path: Path | str | None = None) -> TestSet:
    """Load existing test set or create a new one from dataframe."""
    if output_path is not None:
        target = Path(output_path)
        if target.exists():
            data = read_json(target)
            if isinstance(data, list):
                return TestSet(data)
            if isinstance(data, dict) and "samples" in data:
                return TestSet(data["samples"])
    samples = build_test_set(df, output_path)
    return TestSet(samples)
