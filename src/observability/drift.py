from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def compute_distribution_buckets(values: list[float] | list[int] | pd.Series, buckets: list[tuple[float, float, str]]) -> list[dict[str, Any]]:
    """Compute counts and proportions for predefined value buckets."""
    series = pd.Series(values).dropna()
    total = len(series)
    result = []
    for low, high, label in buckets:
        if high == float("inf"):
            count = int(((series >= low)).sum())
        else:
            count = int(((series >= low) & (series < high)).sum())
        proportion = (count / total) if total > 0 else 0.0
        result.append(
            {
                "label": label,
                "min": low,
                "max": high if high != float("inf") else None,
                "count": count,
                "percentage": round(proportion * 100, 1),
                "proportion": round(proportion, 4),
            }
        )
    return result


def compute_psi(expected_proportions: list[float], actual_proportions: list[float], epsilon: float = 1e-4) -> float:
    """Calculate Population Stability Index (PSI) between two distributions."""
    psi = 0.0
    for exp, act in zip(expected_proportions, actual_proportions, strict=False):
        exp_adj = max(exp, epsilon)
        act_adj = max(act, epsilon)
        psi += (act_adj - exp_adj) * math.log(act_adj / exp_adj)
    return round(float(psi), 4)


def compute_kolmogorov_smirnov(sample1: list[float] | pd.Series, sample2: list[float] | pd.Series) -> tuple[float, float]:
    """Calculate 2-sample Kolmogorov-Smirnov test statistic D and approximate p-value."""
    s1 = np.sort(np.asarray(sample1, dtype=float))
    s2 = np.sort(np.asarray(sample2, dtype=float))
    n1, n2 = len(s1), len(s2)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0

    all_vals = np.concatenate([s1, s2])
    cdf1 = np.searchsorted(s1, all_vals, side="right") / n1
    cdf2 = np.searchsorted(s2, all_vals, side="right") / n2
    d_stat = float(np.max(np.abs(cdf1 - cdf2)))

    # Asymptotic approximation for p-value
    en = math.sqrt((n1 * n2) / (n1 + n2))
    lam = (en + 0.12 + 0.11 / en) * d_stat
    # Kolmogorov distribution approximation
    if lam <= 0.0:
        p_val = 1.0
    else:
        p_val = 2.0 * sum(((-1) ** (k - 1)) * math.exp(-2 * (k**2) * (lam**2)) for k in range(1, 10))
        p_val = max(0.0, min(1.0, float(p_val)))
    return round(d_stat, 4), round(p_val, 4)


def analyze_data_drift(baseline_df: pd.DataFrame, current_df: pd.DataFrame) -> dict[str, Any]:
    """Perform comprehensive data drift analysis comparing current dataset against baseline."""
    age_buckets_def = [
        (0, 30, "< 30 ngày (Rất mới)"),
        (30, 90, "30 - 90 ngày (Mới)"),
        (90, 180, "90 - 180 ngày (Tiêu chuẩn)"),
        (180, float("inf"), "> 180 ngày (Stale / Quá hạn)"),
    ]

    base_age = baseline_df["age_days"] if "age_days" in baseline_df else pd.Series([], dtype=float)
    curr_age = current_df["age_days"] if "age_days" in current_df else pd.Series([], dtype=float)

    base_dist = compute_distribution_buckets(base_age, age_buckets_def)
    curr_dist = compute_distribution_buckets(curr_age, age_buckets_def)

    # PSI calculation
    base_props = [b["proportion"] for b in base_dist]
    curr_props = [b["proportion"] for b in curr_dist]
    age_psi = compute_psi(base_props, curr_props)

    # KS Test
    ks_stat, p_val = compute_kolmogorov_smirnov(base_age, curr_age)

    # Summary length drift
    base_lens = baseline_df["summary"].astype(str).str.len() if "summary" in baseline_df else pd.Series([], dtype=float)
    curr_lens = current_df["summary"].astype(str).str.len() if "summary" in current_df else pd.Series([], dtype=float)
    len_ks_stat, len_p_val = compute_kolmogorov_smirnov(base_lens, curr_lens)

    # Drift decision logic
    if age_psi >= 0.25 or ks_stat >= 0.40 or p_val < 0.05:
        drift_level = "CRITICAL_DRIFT"
        drift_status = "Phát hiện Data Drift nghiêm trọng (Cảnh báo đỏ)"
        alert_color = "#ef4444"
        is_drifted = True
    elif age_psi >= 0.10 or ks_stat >= 0.20:
        drift_level = "MODERATE_DRIFT"
        drift_status = "Phát hiện Data Drift mức độ vừa (Cần theo dõi)"
        alert_color = "#f59e0b"
        is_drifted = True
    else:
        drift_level = "STABLE"
        drift_status = "Phân bố ổn định (Không có Drift)"
        alert_color = "#10b981"
        is_drifted = False

    return {
        "drift_detected": is_drifted,
        "drift_level": drift_level,
        "drift_status": drift_status,
        "alert_color": alert_color,
        "metrics": {
            "age_psi": age_psi,
            "age_ks_statistic": ks_stat,
            "age_p_value": p_val,
            "summary_len_ks": len_ks_stat,
            "baseline_mean_age": round(float(base_age.mean()), 1) if not base_age.empty else 0.0,
            "current_mean_age": round(float(curr_age.mean()), 1) if not curr_age.empty else 0.0,
            "age_mean_shift": round(float(curr_age.mean() - base_age.mean()), 1) if not base_age.empty and not curr_age.empty else 0.0,
            "baseline_count": int(len(baseline_df)),
            "current_count": int(len(current_df)),
        },
        "distributions": {
            "baseline_buckets": base_dist,
            "current_buckets": curr_dist,
        },
    }
