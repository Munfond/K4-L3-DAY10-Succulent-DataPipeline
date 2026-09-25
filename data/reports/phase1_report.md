# Phase 1 — Baseline Data Pipeline Report

## Source summary

| Field | Value |
| --- | --- |
| Source | Crossref REST API |
| Records loaded | 24 |
| Records cleaned | 24 |

## Evaluation metrics

| Metric | Value |
| --- | ---: |
| Samples | 10 |
| Retrieval hit rate | 1.0 |
| Mean token F1 | 0.8 |
| Judge accuracy | 0.8 |
| Mean judge score | 4.2 |

## Quality gate

Overall status: **PASS**
Rows checked: 24

| Expectation | Status |
| --- | --- |
| row_count | PASS |
| paper_id_not_null | PASS |
| title_not_null | PASS |
| text_for_embedding_not_null | PASS |
| paper_id_unique | PASS |
| summary_min_length | PASS |

## Freshness SLA

| Signal | Value |
| --- | --- |
| Latest published | 2026-07-22 |
| Oldest published | 2026-03-28 |
| Stale rows | 1 / 24 |
| Stale ratio | 0.041666666666666664 |
| Freshness status | PASS |
