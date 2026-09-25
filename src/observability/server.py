from __future__ import annotations

import http.server
import json
from pathlib import Path
import socketserver
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from observability.drift import analyze_data_drift


def _get_stage_data(stage_name: str) -> dict[str, Any]:
    settings = load_settings()
    baseline_path = settings.paths.clean_json
    if not baseline_path.exists():
        baseline_path = settings.paths.clean_csv
    baseline_df = pd.read_json(baseline_path) if baseline_path.suffix == ".json" else pd.read_csv(baseline_path)

    stage_map = {
        "baseline": (settings.paths.clean_json, "baseline", settings.paths.embeddings_json),
        "corrupted": (settings.paths.corrupted_clean_json, "corrupted", settings.paths.corrupted_embeddings_json),
        "repaired": (settings.paths.repaired_clean_json, "repaired", settings.paths.repaired_embeddings_json),
    }

    clean_path, report_prefix, _ = stage_map.get(stage_name.lower(), stage_map["baseline"])
    if not clean_path.exists():
        csv_alt = clean_path.with_suffix(".csv")
        clean_path = csv_alt if csv_alt.exists() else baseline_path

    current_df = pd.read_json(clean_path) if clean_path.suffix == ".json" else pd.read_csv(clean_path)

    # Load Quality report
    quality_file = settings.paths.quality_dir / f"{report_prefix}_quality_report.json"
    quality_data = read_json(quality_file) if quality_file.exists() else {"success": False, "expectations": []}

    # Load Freshness report
    freshness_file = settings.paths.freshness_report if stage_name == "baseline" else settings.paths.quality_dir / f"{report_prefix}_freshness_report.json"
    if not freshness_file.exists():
        freshness_file = settings.paths.freshness_report
    freshness_data = read_json(freshness_file) if freshness_file.exists() else {"is_fresh": True, "stale_rows": 0, "total_rows": len(current_df)}

    # Drift Analysis vs Baseline
    drift_data = analyze_data_drift(baseline_df, current_df)

    # Format papers list for UI table
    papers = []
    for _, row in current_df.iterrows():
        age = int(row.get("age_days", 0))
        summary_len = len(str(row.get("summary", "")))
        is_stale = age > 180
        papers.append(
            {
                "paper_id": str(row.get("paper_id", "")),
                "title": str(row.get("title", "")),
                "published": str(row.get("published", "")),
                "authors": str(row.get("authors_joined", "")),
                "categories": str(row.get("categories_joined", "")),
                "age_days": age,
                "summary_length": summary_len,
                "is_stale": is_stale,
                "status": "Stale (>180d)" if is_stale else "Fresh",
            }
        )

    # Metrics
    metrics_map = {
        "baseline": settings.paths.baseline_metrics,
        "corrupted": settings.paths.corrupted_metrics,
        "repaired": settings.paths.repaired_metrics,
    }
    m_file = metrics_map.get(stage_name.lower())
    metrics_data = read_json(m_file) if m_file and m_file.exists() else {}

    return {
        "stage": stage_name,
        "total_documents": len(current_df),
        "quality": quality_data,
        "freshness": freshness_data,
        "drift": drift_data,
        "metrics": metrics_data,
        "papers": papers,
    }


def _get_comparison_summary() -> dict[str, Any]:
    settings = load_settings()
    summary = {}
    for stage in ["baseline", "corrupted", "repaired"]:
        try:
            summary[stage] = _get_stage_data(stage)
        except Exception as e:
            summary[stage] = {"error": str(e)}
    return summary


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Data Observability & Drift Monitor | Day 10 Lab</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #090d16;
      --surface: #111827;
      --surface-border: #1f2937;
      --card-bg: rgba(17, 24, 39, 0.7);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --primary: #6366f1;
      --primary-glow: rgba(99, 102, 241, 0.25);
      --success: #10b981;
      --success-glow: rgba(16, 185, 129, 0.2);
      --warning: #f59e0b;
      --warning-glow: rgba(245, 158, 11, 0.2);
      --danger: #ef4444;
      --danger-glow: rgba(239, 68, 68, 0.25);
      --radius: 12px;
      --font: 'Inter', system-ui, -apple-system, sans-serif;
      --mono: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: var(--font);
      min-height: 100vh;
      line-height: 1.5;
      padding-bottom: 60px;
    }
    .header {
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--surface-border);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 16px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .brand-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #6366f1, #a855f7);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 16px var(--primary-glow);
    }
    .brand-title {
      font-size: 1.25rem;
      font-weight: 700;
      background: linear-gradient(to right, #ffffff, #c7d2fe);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .brand-sub {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .stage-switch {
      display: flex;
      background: #0f172a;
      padding: 4px;
      border-radius: 10px;
      border: 1px solid var(--surface-border);
      gap: 4px;
    }
    .stage-btn {
      background: transparent;
      color: var(--text-muted);
      border: none;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .stage-btn:hover {
      color: var(--text);
    }
    .stage-btn.active {
      background: var(--primary);
      color: #ffffff;
      box-shadow: 0 0 12px var(--primary-glow);
    }
    .stage-btn.active.corrupted-btn {
      background: var(--danger);
      box-shadow: 0 0 12px var(--danger-glow);
    }
    .stage-btn.active.repaired-btn {
      background: var(--success);
      box-shadow: 0 0 12px var(--success-glow);
    }
    .live-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      padding: 4px 10px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.3);
      border-radius: 20px;
      color: var(--success);
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
      70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .container {
      max-width: 1400px;
      margin: 24px auto;
      padding: 0 24px;
    }
    .alert-banner {
      padding: 16px 20px;
      border-radius: var(--radius);
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      backdrop-filter: blur(8px);
      transition: all 0.3s ease;
    }
    .banner-danger {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.4);
      color: #fca5a5;
    }
    .banner-success {
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #6ee7b7;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--surface-border);
      border-radius: var(--radius);
      padding: 20px;
      backdrop-filter: blur(10px);
      transition: all 0.25s ease;
      position: relative;
      overflow: hidden;
    }
    .kpi-card:hover {
      transform: translateY(-2px);
      border-color: rgba(99, 102, 241, 0.4);
      box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.5);
    }
    .kpi-label {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }
    .kpi-value {
      font-size: 1.85rem;
      font-weight: 800;
      color: #ffffff;
      font-family: var(--mono);
    }
    .kpi-footer {
      margin-top: 6px;
      font-size: 0.75rem;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 700;
      font-family: var(--mono);
    }
    .badge-pass { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-fail { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge-warn { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .charts-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 24px;
    }
    @media (max-width: 900px) {
      .charts-grid { grid-template-columns: 1fr; }
    }
    .chart-card {
      background: var(--card-bg);
      border: 1px solid var(--surface-border);
      border-radius: var(--radius);
      padding: 24px;
      backdrop-filter: blur(10px);
    }
    .chart-title {
      font-size: 1rem;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .chart-desc {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 16px;
    }
    .chart-box {
      position: relative;
      height: 280px;
    }
    .section-title {
      font-size: 1.15rem;
      font-weight: 700;
      color: #ffffff;
      margin: 32px 0 16px 0;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .rules-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }
    .rule-card {
      background: #0f172a;
      border: 1px solid var(--surface-border);
      border-radius: 10px;
      padding: 14px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .rule-name {
      font-family: var(--mono);
      font-size: 0.85rem;
      font-weight: 600;
      color: #e2e8f0;
    }
    .table-card {
      background: var(--card-bg);
      border: 1px solid var(--surface-border);
      border-radius: var(--radius);
      overflow: hidden;
      backdrop-filter: blur(10px);
    }
    .table-header-box {
      padding: 16px 20px;
      border-bottom: 1px solid var(--surface-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .search-input {
      background: #090d16;
      border: 1px solid var(--surface-border);
      color: #fff;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      outline: none;
      width: 260px;
    }
    .search-input:focus {
      border-color: var(--primary);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
      text-align: left;
    }
    th {
      background: #0f172a;
      color: var(--text-muted);
      font-weight: 600;
      padding: 12px 18px;
      border-bottom: 1px solid var(--surface-border);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-size: 0.75rem;
    }
    td {
      padding: 12px 18px;
      border-bottom: 1px solid #1e293b;
      color: #e2e8f0;
    }
    tr:hover td {
      background: rgba(30, 41, 59, 0.4);
    }
  </style>
</head>
<body>

  <header class="header">
    <div class="brand">
      <div class="brand-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      </div>
      <div>
        <div class="brand-title">Data Observability & Drift Monitor</div>
        <div class="brand-sub">Nhóm Succulent — K4-L3A-Day10 Data Pipeline</div>
      </div>
    </div>

    <div style="display: flex; align-items: center; gap: 16px;">
      <div class="stage-switch">
        <button class="stage-btn active" id="btn-baseline" onclick="switchStage('baseline')">
          <span>●</span> Baseline (Clean)
        </button>
        <button class="stage-btn corrupted-btn" id="btn-corrupted" onclick="switchStage('corrupted')">
          <span>▲</span> Corrupted (Drifted)
        </button>
        <button class="stage-btn repaired-btn" id="btn-repaired" onclick="switchStage('repaired')">
          <span>✔</span> Repaired (Restored)
        </button>
      </div>

      <div class="live-badge">
        <div class="pulse-dot"></div>
        LIVE OBSERVE
      </div>
    </div>
  </header>

  <div class="container">

    <!-- Drift / Status Banner -->
    <div id="alert-banner" class="alert-banner banner-success">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span id="banner-icon" style="font-size: 1.4rem;">🛡️</span>
        <div>
          <div id="banner-title" style="font-weight: 700; font-size: 0.95rem;">Phân bố dữ liệu đạt chuẩn (Baseline Healthy)</div>
          <div id="banner-desc" style="font-size: 0.8rem; opacity: 0.85;">Dữ liệu sạch, vượt qua 100% Quality Gate của Great Expectations 1.x và Freshness SLA.</div>
        </div>
      </div>
      <div id="banner-metric" style="font-family: var(--mono); font-size: 0.85rem; font-weight: 600;">
        PSI: 0.0000 | KS-Stat: 0.0000
      </div>
    </div>

    <!-- KPI Cards Grid -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Tổng bài báo (Records)</div>
        <div class="kpi-value" id="kpi-docs">24</div>
        <div class="kpi-footer" id="kpi-docs-foot">Dữ liệu nguồn Crossref API</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Quality Gate (GX 1.x)</div>
        <div class="kpi-value" id="kpi-quality"><span class="badge badge-pass">PASSED</span></div>
        <div class="kpi-footer" id="kpi-quality-foot">6/6 Expectations hợp lệ</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Freshness SLA (180d)</div>
        <div class="kpi-value" id="kpi-freshness"><span class="badge badge-pass">HEALTHY</span></div>
        <div class="kpi-footer" id="kpi-freshness-foot">1/24 bài quá hạn (4.1%)</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Retrieval Hit Rate</div>
        <div class="kpi-value" id="kpi-hitrate" style="color: #818cf8;">1.0000</div>
        <div class="kpi-footer">Top-4 Chunks Search</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Mean Token F1</div>
        <div class="kpi-value" id="kpi-f1" style="color: #38bdf8;">0.8000</div>
        <div class="kpi-footer">RAG Answer Quality</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Data Drift Alert</div>
        <div class="kpi-value" id="kpi-drift"><span class="badge badge-pass">STABLE</span></div>
        <div class="kpi-footer" id="kpi-drift-foot">Không có độ trôi dữ liệu</div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-title">
          <span>Biểu đồ Phân bố Độ tuổi Bài báo (`age_days`)</span>
          <span class="badge badge-pass" id="chart-fresh-badge">SLA &le; 180d</span>
        </div>
        <div class="chart-desc">Phân bố số lượng bài báo theo các khoảng thời gian (Số ngày từ ngày xuất bản đến hiện tại).</div>
        <div class="chart-box">
          <canvas id="ageChart"></canvas>
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-title">
          <span>Cảnh báo Data Drift: Baseline vs Trạng thái hiện tại</span>
          <span class="badge" id="chart-drift-badge">KS & PSI Test</span>
        </div>
        <div class="chart-desc">So sánh trực quan tỷ trọng phân bố giữa Baseline sạch và dữ liệu đang quan sát.</div>
        <div class="chart-box">
          <canvas id="driftChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Great Expectations Section -->
    <div class="section-title">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
      </svg>
      Chi tiết Kiểm định Chất lượng (Great Expectations 1.x Ephemeral Gate)
    </div>
    <div class="rules-grid" id="rules-container">
      <!-- Dynamic expectation cards -->
    </div>

    <!-- Data Explorer Table -->
    <div class="section-title">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <polyline points="10 9 9 9 8 9"></polyline>
      </svg>
      Khám phá Dữ liệu Chi tiết & Trạng thái SLA từng bài báo
    </div>

    <div class="table-card">
      <div class="table-header-box">
        <div style="font-weight: 600; font-size: 0.9rem;" id="table-count-label">Hiển thị 24 bài báo</div>
        <input type="text" id="searchInput" class="search-input" placeholder="Tìm theo tiêu đề, DOI, tác giả..." oninput="filterTable()">
      </div>
      <div style="overflow-x: auto;">
        <table id="papersTable">
          <thead>
            <tr>
              <th>DOI / Paper ID</th>
              <th>Tiêu đề bài báo</th>
              <th>Ngày xuất bản</th>
              <th>Tuổi (ngày)</th>
              <th>Độ dài tóm tắt</th>
              <th>Trạng thái SLA</th>
            </tr>
          </thead>
          <tbody id="tableBody">
            <!-- Dynamic rows -->
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <script>
    let currentStage = 'baseline';
    let ageChartInst = null;
    let driftChartInst = null;
    let currentPapers = [];

    async function loadData(stage) {
      try {
        const resp = await fetch(`/api/stage?name=${stage}`);
        const data = await resp.json();
        renderDashboard(data);
      } catch (err) {
        console.error('Lỗi nạp dữ liệu:', err);
      }
    }

    function switchStage(stage) {
      currentStage = stage;
      document.querySelectorAll('.stage-btn').forEach(btn => btn.classList.remove('active'));
      document.getElementById(`btn-${stage}`).classList.add('active');
      loadData(stage);
    }

    function renderDashboard(data) {
      const isCorrupted = data.stage === 'corrupted';
      const isRepaired = data.stage === 'repaired';
      
      // Update Banner
      const banner = document.getElementById('alert-banner');
      const bTitle = document.getElementById('banner-title');
      const bDesc = document.getElementById('banner-desc');
      const bMetric = document.getElementById('banner-metric');
      const bIcon = document.getElementById('banner-icon');

      if (isCorrupted) {
        banner.className = 'alert-banner banner-danger';
        bIcon.innerText = '🚨';
        bTitle.innerText = 'CẢNH BÁO: Phát hiện Data Corruption & Data Drift Nghiêm Trọng!';
        bDesc.innerText = 'Dữ liệu bị tiêm lỗi làm bẩn: Drop bài mới, làm rỗng summary, lùi ngày về 2020. Quality Gate FAILED & Freshness ALERT!';
        bMetric.innerText = `PSI: ${data.drift.metrics.age_psi} | KS-Stat: ${data.drift.metrics.age_ks_statistic}`;
      } else if (isRepaired) {
        banner.className = 'alert-banner banner-success';
        bIcon.innerText = '✨';
        bTitle.innerText = 'ĐÃ PHỤC HỒI: Idempotent Repair Khôi phục 100% Dữ liệu Nguồn';
        bDesc.innerText = 'Dữ liệu đã được nạp lại từ raw snapshot, vượt qua mọi kiểm định chất lượng và lấy lại phân bố ban đầu.';
        bMetric.innerText = `PSI: ${data.drift.metrics.age_psi} | KS-Stat: ${data.drift.metrics.age_ks_statistic}`;
      } else {
        banner.className = 'alert-banner banner-success';
        bIcon.innerText = '🛡️';
        bTitle.innerText = 'Trạng thái Chuẩn: Baseline Healthy & Sạch sẽ';
        bDesc.innerText = 'Dữ liệu sạch, vượt qua 100% Quality Gate của Great Expectations 1.x và Freshness SLA.';
        bMetric.innerText = `PSI: 0.0000 | KS-Stat: 0.0000`;
      }

      // Update KPIs
      document.getElementById('kpi-docs').innerText = data.total_documents;
      
      const qSuccess = data.quality.success;
      document.getElementById('kpi-quality').innerHTML = qSuccess
        ? '<span class="badge badge-pass">PASSED</span>'
        : '<span class="badge badge-fail">FAILED</span>';
      
      const fFresh = data.freshness.is_fresh;
      document.getElementById('kpi-freshness').innerHTML = fFresh
        ? '<span class="badge badge-pass">HEALTHY</span>'
        : '<span class="badge badge-fail">ALERT</span>';
      document.getElementById('kpi-freshness-foot').innerText = `${data.freshness.stale_rows || 0}/${data.total_documents} bài quá hạn (${((data.freshness.stale_ratio || 0)*100).toFixed(1)}%)`;

      const hit = data.metrics.retrieval_hit_rate !== undefined ? Number(data.metrics.retrieval_hit_rate).toFixed(4) : '1.0000';
      const f1 = data.metrics.mean_token_f1 !== undefined ? Number(data.metrics.mean_token_f1).toFixed(4) : '0.8000';
      document.getElementById('kpi-hitrate').innerText = hit;
      document.getElementById('kpi-f1').innerText = f1;

      const driftLevel = data.drift.drift_level;
      let driftBadgeClass = 'badge-pass';
      if (driftLevel === 'CRITICAL_DRIFT') driftBadgeClass = 'badge-fail';
      else if (driftLevel === 'MODERATE_DRIFT') driftBadgeClass = 'badge-warn';
      document.getElementById('kpi-drift').innerHTML = `<span class="badge ${driftBadgeClass}">${driftLevel}</span>`;
      document.getElementById('kpi-drift-foot').innerText = data.drift.drift_status;

      // Update Expectations list
      const rulesBox = document.getElementById('rules-container');
      rulesBox.innerHTML = '';
      (data.quality.expectations || []).forEach(exp => {
        const pass = exp.success;
        const div = document.createElement('div');
        div.className = 'rule-card';
        div.innerHTML = `
          <div>
            <div class="rule-name">${exp.name}</div>
            <div style="font-size: 0.72rem; color: #64748b; margin-top: 2px;">Great Expectations 1.x Rule</div>
          </div>
          <div>
            ${pass ? '<span class="badge badge-pass">✔ PASS</span>' : '<span class="badge badge-fail">✘ FAIL</span>'}
          </div>
        `;
        rulesBox.appendChild(div);
      });

      // Update Charts
      renderAgeChart(data.drift.distributions.current_buckets, isCorrupted);
      renderDriftChart(data.drift.distributions.baseline_buckets, data.drift.distributions.current_buckets);

      // Update Table
      currentPapers = data.papers || [];
      renderTable(currentPapers);
    }

    function renderAgeChart(buckets, isCorrupted) {
      const labels = buckets.map(b => b.label);
      const counts = buckets.map(b => b.count);
      const bgColors = buckets.map((b, idx) => {
        if (idx === 3 && b.count > 0) return '#ef4444'; // Stale (>180d)
        return isCorrupted ? '#f59e0b' : '#6366f1';
      });

      if (ageChartInst) ageChartInst.destroy();
      const ctx = document.getElementById('ageChart').getContext('2d');
      ageChartInst = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Số lượng bài báo',
            data: counts,
            backgroundColor: bgColors,
            borderRadius: 6,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#1e293b' },
              ticks: { color: '#94a3b8' }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#94a3b8', font: { size: 11 } }
            }
          }
        }
      });
    }

    function renderDriftChart(baseBuckets, currBuckets) {
      const labels = baseBuckets.map(b => b.label);
      const basePct = baseBuckets.map(b => b.percentage);
      const currPct = currBuckets.map(b => b.percentage);

      if (driftChartInst) driftChartInst.destroy();
      const ctx = document.getElementById('driftChart').getContext('2d');
      driftChartInst = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Baseline (%)',
              data: basePct,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              fill: true,
              tension: 0.3,
              pointRadius: 5,
            },
            {
              label: 'Hiện tại (%)',
              data: currPct,
              borderColor: '#f43f5e',
              backgroundColor: 'rgba(244, 63, 94, 0.15)',
              fill: true,
              tension: 0.3,
              pointRadius: 5,
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: '#cbd5e1' }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#1e293b' },
              ticks: { color: '#94a3b8', callback: v => v + '%' }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#94a3b8', font: { size: 11 } }
            }
          }
        }
      });
    }

    function renderTable(papers) {
      const tbody = document.getElementById('tableBody');
      tbody.innerHTML = '';
      document.getElementById('table-count-label').innerText = `Hiển thị ${papers.length} bài báo`;

      papers.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-family: var(--mono); color: #818cf8; font-size: 0.78rem;">${escapeHtml(p.paper_id)}</td>
          <td style="font-weight: 500; max-width: 420px;">${escapeHtml(p.title)}</td>
          <td style="font-family: var(--mono); color: #94a3b8;">${p.published}</td>
          <td style="font-family: var(--mono); font-weight: 700; color: ${p.age_days > 180 ? '#f87171' : '#34d399'};">${p.age_days}d</td>
          <td style="font-family: var(--mono);">${p.summary_length} ký tự</td>
          <td><span class="badge ${p.is_stale ? 'badge-fail' : 'badge-pass'}">${p.status}</span></td>
        `;
        tbody.appendChild(tr);
      });
    }

    function filterTable() {
      const q = document.getElementById('searchInput').value.toLowerCase();
      const filtered = currentPapers.filter(p => 
        p.title.toLowerCase().includes(q) ||
        p.paper_id.toLowerCase().includes(q) ||
        p.authors.toLowerCase().includes(q)
      );
      renderTable(filtered);
    }

    function escapeHtml(str) {
      return (str || '').replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
      );
    }

    // Initial Load
    loadData('baseline');

    // Auto-refresh every 6 seconds
    setInterval(() => {
      loadData(currentStage);
    }, 6000);
  </script>
</body>
</html>
"""


class ObservabilityHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
            return

        if path == "/api/status":
            summary = _get_comparison_summary()
            self._send_json(summary)
            return

        if path == "/api/stage":
            qs = parse_qs(parsed.query)
            stage_name = qs.get("name", ["baseline"])[0]
            stage_data = _get_stage_data(stage_name)
            self._send_json(stage_data)
            return

        # Fallback to standard handler
        super().do_GET()

    def _send_json(self, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


def run_server(port: int = 8501, host: str = "0.0.0.0") -> None:
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((host, port), ObservabilityHandler) as httpd:
        print(f"🚀 Observability Web Dashboard đang chạy tại: http://localhost:{port}")
        print(f"📡 API Status Endpoint: http://localhost:{port}/api/status")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Đã dừng Web Dashboard server.")
