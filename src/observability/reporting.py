from __future__ import annotations

from typing import Any

from core.utils import write_text


def _value(payload: dict[str, Any], key: str, default: str = "N/A") -> Any:
    return payload.get(key, default)


def _metric_row(name: str, baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]) -> str:
    return f"| `{name}` | {_value(baseline, name)} | {_value(corrupted, name)} | {_value(repaired, name)} |"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline artifact used for the CP3 review."""
    checks = quality.get("expectations", [])
    check_rows = "\n".join(f"| {item['name']} | {'PASS' if item['success'] else 'FAIL'} |" for item in checks)
    report = f"""# Phase 1 — Baseline Data Pipeline Report

## Source summary

| Field | Value |
| --- | --- |
| Source | {_value(source_summary, 'source', _value(source_summary, 'source_api'))} |
| Records loaded | {_value(source_summary, 'records_loaded', _value(source_summary, 'total_records'))} |
| Records cleaned | {_value(source_summary, 'records_cleaned', _value(source_summary, 'cleaned_records'))} |

## Evaluation metrics

| Metric | Value |
| --- | ---: |
| Samples | {_value(metrics, 'samples')} |
| Retrieval hit rate | {_value(metrics, 'retrieval_hit_rate')} |
| Mean token F1 | {_value(metrics, 'mean_token_f1')} |
| Judge accuracy | {_value(metrics, 'judge_accuracy')} |
| Mean judge score | {_value(metrics, 'mean_judge_score')} |

## Quality gate

Overall status: **{'PASS' if quality.get('success') else 'FAIL'}**
Rows checked: {quality.get('rows_checked', 'N/A')}

| Expectation | Status |
| --- | --- |
{check_rows or '| No checks recorded | N/A |'}

## Freshness SLA

| Signal | Value |
| --- | --- |
| Latest published | {_value(freshness, 'latest_published')} |
| Oldest published | {_value(freshness, 'oldest_published')} |
| Stale rows | {_value(freshness, 'stale_rows')} / {_value(freshness, 'total_rows')} |
| Stale ratio | {_value(freshness, 'stale_ratio')} |
| Freshness status | {'PASS' if freshness.get('is_fresh') else 'ALERT'} |
"""
    write_text(report_path, report)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write a three-state evidence report for the corruption and repair flow."""
    report = f"""# Corruption & Repair Comparison Report

## RAG evaluation comparison

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
{_metric_row('retrieval_hit_rate', baseline_metrics, corrupted_metrics, repaired_metrics)}
{_metric_row('mean_token_f1', baseline_metrics, corrupted_metrics, repaired_metrics)}
{_metric_row('judge_accuracy', baseline_metrics, corrupted_metrics, repaired_metrics)}
{_metric_row('mean_judge_score', baseline_metrics, corrupted_metrics, repaired_metrics)}

## Data quality comparison

| Signal | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Quality gate | PASS | {'PASS' if corrupted_quality.get('success') else 'FAIL'} | {'PASS' if repaired_quality.get('success') else 'FAIL'} |
| Rows checked | N/A | {_value(corrupted_quality, 'rows_checked')} | {_value(repaired_quality, 'rows_checked')} |
| Freshness status | N/A | {'PASS' if corrupted_freshness.get('is_fresh') else 'ALERT'} | {'PASS' if repaired_freshness.get('is_fresh') else 'ALERT'} |
| Stale rows | N/A | {_value(corrupted_freshness, 'stale_rows')} / {_value(corrupted_freshness, 'total_rows')} | {_value(repaired_freshness, 'stale_rows')} / {_value(repaired_freshness, 'total_rows')} |

## Conclusion

The corrupted run is expected to surface quality or freshness alerts and degrade retrieval/answer metrics. Repair is accepted only when the repaired data passes the quality gate, meets the freshness SLA, and its evaluation metrics recover toward the baseline.
"""
    write_text(report_path, report)
