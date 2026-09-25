from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import great_expectations as gx

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate a cleaned dataframe with an in-memory Great Expectations 1.x gate."""
    required_columns = {"paper_id", "title", "text_for_embedding", "summary", "age_days"}
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Cannot run quality checks; missing columns: {', '.join(missing_columns)}")

    # GX 1.x ephemeral context: no datasource configuration is persisted to disk.
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df.copy()})

    expectations = [
        ("row_count", gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)),
        ("paper_id_not_null", gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id")),
        ("title_not_null", gx.expectations.ExpectColumnValuesToNotBeNull(column="title")),
        (
            "text_for_embedding_not_null",
            gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        ),
        ("paper_id_unique", gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id")),
        (
            "summary_min_length",
            gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
        ),
    ]

    results: list[dict[str, Any]] = []
    for name, expectation in expectations:
        validation = batch.validate(expectation)
        results.append(
            {
                "name": name,
                "success": bool(validation.success),
                "result": validation.result,
            }
        )

    payload: dict[str, Any] = {
        "report_name": report_name,
        "rows_checked": int(len(df)),
        "success": all(item["success"] for item in results),
        "expectations": results,
    }
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Measure the proportion of documents beyond the freshness SLA."""
    if "age_days" not in df.columns or "published" not in df.columns:
        raise ValueError("Freshness report requires 'published' and 'age_days' columns.")

    ages = pd.to_numeric(df["age_days"], errors="coerce")
    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    total_rows = int(len(df))
    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    payload: dict[str, Any] = {
        "generated_on": date.today().isoformat(),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "latest_published": published.max().date().isoformat() if published.notna().any() else None,
        "oldest_published": published.min().date().isoformat() if published.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "is_fresh": bool(total_rows and stale_ratio <= 0.25),
    }
    write_json(report_path, payload)
    return payload
