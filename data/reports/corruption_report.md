# Corruption & Repair Comparison Report

## RAG evaluation comparison

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0 | 0.7 | 1.0 |
| `mean_token_f1` | 0.8 | 0.7 | 0.8 |
| `judge_accuracy` | 0.8 | 0.7 | 0.8 |
| `mean_judge_score` | 4.2 | 3.8 | 4.2 |

## Data quality comparison

| Signal | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Quality gate | PASS | FAIL | PASS |
| Rows checked | N/A | 22 | 24 |
| Freshness status | N/A | ALERT | PASS |
| Stale rows | N/A | 11 / 22 | 1 / 24 |

## Conclusion

The corrupted run is expected to surface quality or freshness alerts and degrade retrieval/answer metrics. Repair is accepted only when the repaired data passes the quality gate, meets the freshness SLA, and its evaluation metrics recover toward the baseline.
