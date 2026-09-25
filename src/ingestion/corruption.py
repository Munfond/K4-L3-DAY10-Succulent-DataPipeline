from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str | None = None) -> pd.DataFrame:
    """Simulate multiple data corruption scenarios on a cleaned papers dataset.

    Steps applied:
    1. Drop latest records (e.g. 20% newest by published date).
    2. Blank summary on 2 records.
    3. Inject adversarial noise into summary on 2 records.
    4. Truncate title on 2 records.
    5. Make published date stale on up to 8 records (to trigger freshness checks).
    6. Add duplicate rows (2 records).
    7. Rebuild text_for_embedding for all corrupted records.
    8. Write corruption log to output_log_path.
    """
    corrupted = df.copy()
    corruption_log: dict[str, Any] = {
        "applied_corruptions": [],
        "timestamp": now_utc().isoformat(),
    }

    # 1. Drop latest records (20% newest by published date)
    if "published" in corrupted.columns and len(corrupted) > 0:
        n_drop = max(1, int(len(corrupted) * 0.20))
        corrupted = corrupted.sort_values(by="published", ascending=False).reset_index(drop=True)
        dropped_ids = corrupted.iloc[:n_drop]["paper_id"].tolist()
        corrupted = corrupted.iloc[n_drop:].reset_index(drop=True)
        corruption_log["applied_corruptions"].append(
            {
                "scenario": "drop_latest_records",
                "dropped_count": n_drop,
                "dropped_paper_ids": dropped_ids,
            }
        )

    # 2. Blank summary on 2 records
    if len(corrupted) >= 2:
        blanked_ids = corrupted.iloc[0:2]["paper_id"].tolist()
        corrupted.loc[0:1, "summary"] = ""
        if "summary_chars" in corrupted.columns:
            corrupted.loc[0:1, "summary_chars"] = 0
        corruption_log["applied_corruptions"].append(
            {"scenario": "blank_summary", "affected_paper_ids": blanked_ids}
        )

    # 3. Inject noise into summary on 2 records
    if len(corrupted) >= 4:
        noisy_ids = corrupted.iloc[2:4]["paper_id"].tolist()
        for idx in range(2, 4):
            corrupted.at[idx, "summary"] = (
                str(corrupted.at[idx, "summary"])
                + " [CORRUPTED_ADVERSARIAL_NOISE_TOKEN_XYZ_9999]"
            )
            if "summary_chars" in corrupted.columns:
                corrupted.at[idx, "summary_chars"] = len(corrupted.at[idx, "summary"])
        corruption_log["applied_corruptions"].append(
            {"scenario": "inject_noise", "affected_paper_ids": noisy_ids}
        )

    # 4. Truncate title on 2 records (< 8 chars)
    if len(corrupted) >= 6:
        trunc_ids = corrupted.iloc[4:6]["paper_id"].tolist()
        for idx in range(4, 6):
            corrupted.at[idx, "title"] = str(corrupted.at[idx, "title"])[:6]
        corruption_log["applied_corruptions"].append(
            {"scenario": "truncate_title", "affected_paper_ids": trunc_ids}
        )

    # 5. Stale date on 8 records (age_days > 180 to trigger freshness alert)
    if len(corrupted) >= 8:
        stale_count = min(8, len(corrupted))
        stale_ids = corrupted.iloc[:stale_count]["paper_id"].tolist()
        stale_date_str = "2020-01-01"
        corrupted.loc[: stale_count - 1, "published"] = stale_date_str
        if "updated" in corrupted.columns:
            corrupted.loc[: stale_count - 1, "updated"] = stale_date_str
        ref_dt = now_utc().date()
        stale_dt = pd.to_datetime(stale_date_str).date()
        corrupted.loc[: stale_count - 1, "age_days"] = (ref_dt - stale_dt).days
        corruption_log["applied_corruptions"].append(
            {"scenario": "stale_date", "affected_paper_ids": stale_ids, "new_date": stale_date_str}
        )

    # 6. Duplicate rows: duplicate 2 records
    if len(corrupted) >= 2:
        dup_rows = corrupted.iloc[0:2].copy()
        corrupted = pd.concat([corrupted, dup_rows], ignore_index=True)
        corruption_log["applied_corruptions"].append(
            {"scenario": "duplicate_rows", "duplicated_paper_ids": dup_rows["paper_id"].tolist()}
        )

    # 7. Rebuild text_for_embedding for all corrupted records
    new_embedding_texts = []
    for _, row in corrupted.iterrows():
        new_text = (
            f"Title: {row['title']}\n"
            f"Authors: {row.get('authors_joined', '')}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row.get('categories_joined', '')}\n"
            f"Summary: {row['summary']}"
        )
        new_embedding_texts.append(new_text)
    corrupted["text_for_embedding"] = new_embedding_texts

    # 8. Write corruption log
    if output_log_path is not None:
        write_json(Path(output_log_path), corruption_log)

    return corrupted
