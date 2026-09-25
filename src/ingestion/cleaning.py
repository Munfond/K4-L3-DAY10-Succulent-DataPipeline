from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import compact_join, normalize_whitespace, now_utc, write_csv, write_json
from ingestion.crossref import PaperRecord, load_raw_records


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into an embedding-ready and standardized pandas DataFrame."""
    rows: list[dict[str, Any]] = []
    ref_dt = run_date.date() if isinstance(run_date, datetime) else run_date

    for record in records:
        paper_id = normalize_whitespace(record.paper_id)
        if not paper_id:
            continue

        title = normalize_whitespace(record.title)
        if not title:
            continue

        summary = normalize_whitespace(record.summary)
        authors = [normalize_whitespace(a) for a in record.authors if a]
        authors_joined = compact_join(authors, sep=", ")

        categories = [normalize_whitespace(c) for c in record.categories if c]
        categories_joined = compact_join(categories, sep=", ")
        primary_category = normalize_whitespace(
            record.primary_category or (categories[0] if categories else "General")
        )

        published = normalize_whitespace(record.published[:10]) if record.published else ""
        updated = (
            normalize_whitespace(record.updated[:10])
            if record.updated
            else (published or "")
        )

        age_days = 0
        if published:
            try:
                pub_dt = datetime.strptime(published, "%Y-%m-%d").date()
                age_days = (ref_dt - pub_dt).days
            except Exception:
                age_days = 0

        summary_chars = len(summary)

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "age_days": age_days,
                "summary_chars": summary_chars,
                "text_for_embedding": text_for_embedding,
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": record.comment,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        # Deduplicate strictly on primary key paper_id
        df = df.drop_duplicates(subset=["paper_id"], keep="first")
        # Ensure compulsory fields are not empty
        df = df[df["paper_id"].astype(str).str.strip().ne("") & df["title"].astype(str).str.strip().ne("")]
        df = df.reset_index(drop=True)

    return df


def repair_from_raw_snapshot(settings: Settings, run_date: datetime | None = None) -> pd.DataFrame:
    """Idempotently repair the cleaned dataset from trusted raw snapshot data.

    Guarantees that regardless of previous corrupted states or repeated invocations,
    the pipeline deterministically reproduces the exact clean baseline dataset.
    Writes repaired clean data to repaired_clean_csv and repaired_clean_json.
    """
    raw_path = settings.paths.raw_records_json
    if not raw_path.exists():
        raw_path = settings.paths.raw_api_response

    raw_records = load_raw_records(raw_path)
    ref_time = run_date or now_utc()
    repaired_df = build_clean_dataframe(raw_records, ref_time)

    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    return repaired_df

