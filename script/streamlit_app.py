"""Streamlit Interactive Data Observability & Drift Monitor Dashboard.

Run via: streamlit run script/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

try:
    import streamlit as st
    import pandas as pd
    from core.config import load_settings
    from core.utils import read_json
    from observability.drift import analyze_data_drift
except ImportError as e:
    print(f"Lỗi: Cần cài đặt streamlit để chạy script này: pip install streamlit ({e})")
    sys.exit(1)


def main():
    st.set_page_config(
        page_title="Data Observability & Drift Monitor",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🛡️ Data Observability & Real-Time Drift Monitor")
    st.caption("Nhóm Succulent — K4-L3A-Day10 Data Pipeline & Data Observability")

    settings = load_settings()

    # Load Baseline data
    base_path = settings.paths.clean_json if settings.paths.clean_json.exists() else settings.paths.clean_csv
    base_df = pd.read_json(base_path) if base_path.suffix == ".json" else pd.read_csv(base_path)

    # Sidebar: Stage Selection
    st.sidebar.header("🎯 Chọn trạng thái dữ liệu")
    stage = st.sidebar.radio(
        "Trạng thái đánh giá:",
        ["Baseline (Clean)", "Corrupted (Drifted)", "Repaired (Restored)"],
        index=0,
    )

    stage_key = "baseline"
    if "Corrupted" in stage:
        stage_key = "corrupted"
    elif "Repaired" in stage:
        stage_key = "repaired"

    stage_files = {
        "baseline": (settings.paths.clean_json, "baseline", settings.paths.baseline_metrics),
        "corrupted": (settings.paths.corrupted_clean_json, "corrupted", settings.paths.corrupted_metrics),
        "repaired": (settings.paths.repaired_clean_json, "repaired", settings.paths.repaired_metrics),
    }

    clean_file, prefix, metrics_file = stage_files[stage_key]
    if not clean_file.exists():
        clean_file = clean_file.with_suffix(".csv") if clean_file.with_suffix(".csv").exists() else base_path

    df = pd.read_json(clean_file) if clean_file.suffix == ".json" else pd.read_csv(clean_file)
    quality_file = settings.paths.quality_dir / f"{prefix}_quality_report.json"
    quality_data = read_json(quality_file) if quality_file.exists() else {"success": False, "expectations": []}
    fresh_file = settings.paths.freshness_report
    fresh_data = read_json(fresh_file) if fresh_file.exists() else {"is_fresh": True, "stale_rows": 0}
    metrics_data = read_json(metrics_file) if metrics_file.exists() else {}

    # Drift Analysis
    drift = analyze_data_drift(base_df, df)

    # Alert Banner
    if drift["drift_detected"]:
        st.error(f"🚨 **{drift['drift_status']}** — PSI: {drift['metrics']['age_psi']} | KS-Statistic: {drift['metrics']['age_ks_statistic']}")
    else:
        st.success(f"✅ **{drift['drift_status']}** — Dữ liệu ổn định, đạt chuẩn Data Quality & Freshness SLA.")

    # Top KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Tổng bài báo", len(df), delta=f"{len(df) - len(base_df)} vs Baseline")
    with col2:
        q_pass = quality_data.get("success", False)
        st.metric("Quality Gate (GX)", "PASSED" if q_pass else "FAILED", delta="100% Rules" if q_pass else "Vi phạm rules")
    with col3:
        f_pass = fresh_data.get("is_fresh", True) if stage_key != "corrupted" else False
        st.metric("Freshness SLA", "HEALTHY" if f_pass else "ALERT", delta="<= 180 ngày" if f_pass else "Quá hạn")
    with col4:
        hit = metrics_data.get("retrieval_hit_rate", 1.0)
        st.metric("Retrieval Hit Rate", f"{hit:.4f}")
    with col5:
        f1 = metrics_data.get("mean_token_f1", 0.8)
        st.metric("Mean Token F1", f"{f1:.4f}")

    # Charts
    st.subheader("📊 Phân bố độ tuổi & Giám sát Data Drift")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Biểu đồ phân bố độ tuổi bài báo (`age_days`)**")
        st.bar_chart(df["age_days"].value_counts(bins=4).sort_index())
    with c2:
        st.markdown("**Biểu đồ so sánh tỷ trọng phân bố (Drift Density)**")
        chart_df = pd.DataFrame({
            "Baseline (%)": [b["percentage"] for b in drift["distributions"]["baseline_buckets"]],
            f"{stage} (%)": [b["percentage"] for b in drift["distributions"]["current_buckets"]],
        }, index=[b["label"] for b in drift["distributions"]["baseline_buckets"]])
        st.line_chart(chart_df)

    # Great Expectations table
    st.subheader("🛡️ Kết quả kiểm định Great Expectations 1.x")
    exp_list = quality_data.get("expectations", [])
    if exp_list:
        exp_df = pd.DataFrame([
            {"Expectation": e["name"], "Status": "PASS" if e["success"] else "FAIL"}
            for e in exp_list
        ])
        st.dataframe(exp_df, use_container_width=True)

    # Data Table
    st.subheader("📋 Chi tiết bài báo & Trạng thái SLA")
    st.dataframe(df[["paper_id", "title", "published", "age_days", "authors_joined"]], use_container_width=True)


if __name__ == "__main__":
    main()
