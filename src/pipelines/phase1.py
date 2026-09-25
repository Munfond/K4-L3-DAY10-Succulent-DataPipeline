from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import (
    ensure_artifact_dirs,
    first_sentence,
    now_utc,
    read_json,
    write_csv,
    write_json,
    write_text,
)
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from retrieval.index import LocalEmbeddingIndex

logger = logging.getLogger(__name__)


def _build_default_test_set(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Build a deterministic 10-question evaluation set covering 4 query types."""
    records = df.to_dict(orient="records")
    if len(records) < 10:
        raise ValueError(f"Need at least 10 records to build test set, got {len(records)}")

    test_set: list[dict[str, Any]] = []

    # 1-3: summary questions
    for idx, row in enumerate(records[0:3]):
        test_set.append(
            {
                "id": f"eval_{idx+1:03d}",
                "question_type": "summary",
                "question": f"What is the summary of the paper '{row['title']}'?",
                "ground_truth": first_sentence(row["summary"]),
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    # 4-6: authors questions
    for idx, row in enumerate(records[3:6], start=3):
        test_set.append(
            {
                "id": f"eval_{idx+1:03d}",
                "question_type": "authors",
                "question": f"Who authored the paper '{row['title']}'?",
                "ground_truth": row["authors_joined"],
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    # 7-8: date questions
    for idx, row in enumerate(records[6:8], start=6):
        test_set.append(
            {
                "id": f"eval_{idx+1:03d}",
                "question_type": "date",
                "question": f"When was the paper '{row['title']}' published?",
                "ground_truth": row["published"],
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    # 9-10: categories questions
    for idx, row in enumerate(records[8:10], start=8):
        test_set.append(
            {
                "id": f"eval_{idx+1:03d}",
                "question_type": "categories",
                "question": f"What categories describe the paper '{row['title']}'?",
                "ground_truth": row["categories_joined"],
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    return test_set


def _get_or_create_test_set(df: pd.DataFrame, settings: Settings) -> list[dict[str, Any]]:
    """Retrieve existing test set or construct a new one."""
    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        return read_json(settings.paths.eval_testset)

    try:
        from evaluation.testset import build_test_set
        return build_test_set(df, settings.paths.eval_testset)
    except NotImplementedError:
        test_set = _build_default_test_set(df)
        write_json(settings.paths.eval_testset, test_set)
        return test_set


def _run_quality_and_freshness(
    df: pd.DataFrame, settings: Settings, report_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run data quality expectations and freshness SLA checks."""
    try:
        from observability.quality import build_freshness_report, run_data_quality_checks
        q_rep = run_data_quality_checks(df, settings, report_name)
        f_rep = build_freshness_report(df, settings, settings.paths.freshness_report)
        return q_rep, f_rep
    except NotImplementedError:
        # Fallback implementation verifying the 4 required Expectations + Freshness SLA
        total_rows = len(df)
        null_paper_id = int(df["paper_id"].isna().sum()) if "paper_id" in df else total_rows
        null_title = int(df["title"].isna().sum()) if "title" in df else total_rows
        null_embedding_text = (
            int(df["text_for_embedding"].isna().sum()) if "text_for_embedding" in df else total_rows
        )
        unique_paper_ids = int(df["paper_id"].nunique()) if "paper_id" in df else 0
        is_unique = (unique_paper_ids == total_rows)
        short_summaries = int((df["summary"].astype(str).str.len() < 30).sum()) if "summary" in df else total_rows

        row_count_valid = 5 <= total_rows <= 5000
        null_valid = (null_paper_id == 0 and null_title == 0 and null_embedding_text == 0)
        summary_len_valid = (short_summaries == 0)

        quality_success = bool(row_count_valid and null_valid and is_unique and summary_len_valid)

        q_rep = {
            "report_name": report_name,
            "success": quality_success,
            "total_rows": total_rows,
            "expectations": {
                "ExpectTableRowCountToBeBetween": {"success": row_count_valid, "observed": total_rows},
                "ExpectColumnValuesToNotBeNull": {
                    "success": null_valid,
                    "null_counts": {
                        "paper_id": null_paper_id,
                        "title": null_title,
                        "text_for_embedding": null_embedding_text,
                    },
                },
                "ExpectColumnValuesToBeUnique": {
                    "success": is_unique,
                    "unique_count": unique_paper_ids,
                    "total_count": total_rows,
                },
                "ExpectColumnValueLengthsToBeBetween": {
                    "success": summary_len_valid,
                    "short_summary_count": short_summaries,
                },
            },
        }

        # Freshness SLA: stale if age_days > 180
        stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum()) if "age_days" in df else 0
        stale_ratio = stale_rows / total_rows if total_rows > 0 else 0.0
        is_fresh = stale_ratio <= 0.25

        f_rep = {
            "total_rows": total_rows,
            "stale_rows": stale_rows,
            "stale_ratio": round(stale_ratio, 4),
            "freshness_threshold_days": settings.freshness_threshold_days,
            "is_fresh": is_fresh,
            "status": "HEALTHY" if is_fresh else "STALE_ALERT",
        }

        target_q_path = (
            settings.paths.baseline_quality_report
            if report_name == "baseline"
            else settings.paths.corrupted_quality_report
        )
        write_json(target_q_path, q_rep)
        write_json(settings.paths.freshness_report, f_rep)
        return q_rep, f_rep


def _write_phase1_report(
    settings: Settings,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Generate Markdown report for Phase 1 baseline pipeline."""
    try:
        from observability.reporting import generate_phase1_report
        generate_phase1_report(
            settings.paths.baseline_report, source_summary, metrics, quality, freshness
        )
    except NotImplementedError:
        content = f"""# Phase 1 Baseline Pipeline Report

## 1. Source Data Ingestion Summary
- **Source API:** {source_summary.get('source_api', 'Crossref')}
- **Total Records Ingested:** {source_summary.get('raw_records_count', 0)}
- **Clean Records Processed:** {source_summary.get('clean_records_count', 0)}
- **Run Date:** {source_summary.get('run_date', 'N/A')}

## 2. Quality Gate & Freshness SLA
- **Great Expectations 1.x Status:** {'✅ PASSED' if quality.get('success') else '❌ FAILED'}
- **Freshness SLA Status:** {'✅ HEALTHY' if freshness.get('is_fresh') else '⚠️ STALE ALERT'}
- **Stale Records (> 180 days):** {freshness.get('stale_rows', 0)} / {freshness.get('total_rows', 0)} ({freshness.get('stale_ratio', 0.0) * 100:.1f}%)

## 3. RAG Retrieval & Benchmark Metrics
| Metric | Value | Target |
| :--- | :--- | :--- |
| **Retrieval Hit Rate** | {metrics.get('retrieval_hit_rate', 0.0):.4f} | >= 0.80 |
| **Mean Token F1** | {metrics.get('mean_token_f1', 0.0):.4f} | >= 0.70 |
| **Judge Accuracy** | {metrics.get('judge_accuracy', 0.0):.4f} | >= 0.80 |
| **Mean Judge Score** | {metrics.get('mean_judge_score', 0.0):.2f} / 5.0 | >= 3.5 |

## 4. Vector Store Architecture
- **Embedding Model:** {settings.embedding_model}
- **ChromaDB Collection:** `{settings.baseline_collection_name}`
- **Distance Metric:** Cosine Similarity
"""
        write_text(settings.paths.baseline_report, content)


def main() -> None:
    """Execute baseline pipeline end-to-end (Phase 1)."""
    settings = load_settings()
    ensure_artifact_dirs(settings.paths)

    print("=" * 60)
    print(">>> STARTING PHASE 1: BASELINE DATA PIPELINE")
    print("=" * 60)

    # 1 & 2. Ingestion
    print("\n[Step 1/6] Ingesting Crossref academic records...")
    records = fetch_source_records(settings)
    print(f"  -> Successfully loaded {len(records)} raw records.")

    # 3 & 4. Cleaning & Schema Transformation
    print("\n[Step 2/6] Cleaning data, computing age_days & text_for_embedding...")
    run_time = now_utc()
    clean_df = build_clean_dataframe(records, run_date=run_time)
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))
    print(f"  -> Cleaned dataset saved: {len(clean_df)} documents.")

    # 5. Chroma Vector Store Indexing
    print("\n[Step 3/6] Indexing documents in ChromaDB vector store...")
    index = LocalEmbeddingIndex.build(
        clean_df, settings, embeddings_output_path=settings.paths.embeddings_json
    )
    print(f"  -> Chroma collection '{settings.baseline_collection_name}' ready with {len(index.documents)} vectors.")

    # 6. Benchmark Test Set Preparation
    print("\n[Step 4/6] Preparing benchmark evaluation set (10 questions across 4 categories)...")
    test_set = _get_or_create_test_set(clean_df, settings)
    print(f"  -> Test set ready with {len(test_set)} ground truth question-answer pairs.")

    # 7. Pipeline Evaluation
    print("\n[Step 5/6] Evaluating RAG baseline performance...")
    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    summary = bundle.summary
    print(f"  -> Retrieval Hit Rate: {summary['retrieval_hit_rate']:.4f}")
    print(f"  -> Mean Token F1:     {summary['mean_token_f1']:.4f}")
    print(f"  -> Judge Accuracy:     {summary['judge_accuracy']:.4f}")

    # 8 & 9. Data Observability Quality Gate & Reporting
    print("\n[Step 6/6] Running Data Quality Gate & generating Phase 1 report...")
    quality_rep, freshness_rep = _run_quality_and_freshness(clean_df, settings, "baseline")
    source_summary = {
        "source": settings.source_api,
        "source_api": settings.source_api,
        "records_loaded": len(records),
        "total_records": len(records),
        "raw_records_count": len(records),
        "records_cleaned": len(clean_df),
        "cleaned_records": len(clean_df),
        "clean_records_count": len(clean_df),
        "run_date": run_time.isoformat(),
    }
    _write_phase1_report(settings, source_summary, summary, quality_rep, freshness_rep)
    print(f"  -> Phase 1 Report generated at: {settings.paths.baseline_report}")

    print("\n" + "=" * 60)
    print(">>> PHASE 1 COMPLETED SUCCESSFULLY!")
    print("=" * 60)

