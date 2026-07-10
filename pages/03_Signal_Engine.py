"""
pages/03_Signal_Engine.py
==========================
Unified Signal Engine page. Shows how account_age, report_volume,
device_reuse, ip_region, and toxicity fuse into one composite_risk_score
-- signal fusion, not a single if:spam:risk=90 rule.

Everything here comes from src/repositories/signal_repository.py, which
reads scores that scripts/generate_signal_scores.py computed from real
account/comment/report data (see that script's docstring).
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.signal_repository import SignalRepository
from src.engines.signal_engine import SignalEngine

st.set_page_config(layout="wide")
st.title("Unified Signal Engine")
st.caption(
    "Five independent signals, fused into one composite risk score. "
    "No single signal decides the outcome on its own."
)

repo = SignalRepository()
stats = repo.get_engine_stats()

# ── Overview KPIs ────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Accounts Scored", f"{stats.get('total_accounts', 0):,}")
col2.metric("Average Composite Risk", f"{stats.get('avg_composite', 0):.3f}")
col3.metric("Lowest Score", f"{stats.get('min_composite', 0):.3f}")
col4.metric("Highest Score", f"{stats.get('max_composite', 0):.3f}")

st.divider()

left, right = st.columns([1, 1])

# ── Weight breakdown ─────────────────────────────────────────────────────
with left:
    st.subheader("Signal Weights")
    st.caption("How much each signal contributes to the composite score.")

    weights = repo.get_weights()
    fig = go.Figure(go.Bar(
        x=list(weights.values()),
        y=list(weights.keys()),
        orientation="h",
        marker_color="#4C6FFF",
        text=[f"{v:.0%}" for v in weights.values()],
        textposition="outside",
    ))
    fig.update_layout(
        xaxis_title="Weight", yaxis_title=None,
        margin=dict(l=10, r=10, t=10, b=10), height=280,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Platform Signal Averages")
    avg_labels = ["Account Age", "Report Volume", "Device Reuse", "IP Region", "Toxicity"]
    avg_values = [
        stats.get("avg_age", 0), stats.get("avg_reports", 0),
        stats.get("avg_device", 0), stats.get("avg_ip", 0),
        stats.get("avg_toxicity", 0),
    ]
    fig2 = go.Figure(go.Bar(x=avg_labels, y=avg_values, marker_color="#8C9EFF"))
    fig2.update_layout(yaxis_range=[0, 1], margin=dict(l=10, r=10, t=10, b=10), height=280)
    st.plotly_chart(fig2, use_container_width=True)

# ── Score distribution ───────────────────────────────────────────────────
with right:
    st.subheader("Composite Risk Score Distribution")
    st.caption("Where every account falls, in 0.1-wide buckets.")

    dist = repo.get_score_distribution()
    fig3 = go.Figure(go.Bar(
        x=[f"{d['bucket']:.1f}" for d in dist],
        y=[d["count"] for d in dist],
        marker_color="#FF6F61",
    ))
    fig3.update_layout(
        xaxis_title="Composite Risk Score", yaxis_title="Accounts",
        margin=dict(l=10, r=10, t=10, b=10), height=590,
    )
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Top risk accounts table with per-signal breakdown ────────────────────
st.subheader("Highest-Risk Accounts")
st.caption("Top 20 by composite score, with each contributing signal shown.")

top = repo.get_top_risk_accounts(limit=20)
if top:
    st.dataframe(
        top,
        use_container_width=True,
        column_config={
            "composite_risk_score": st.column_config.ProgressColumn(
                "Composite Risk", min_value=0, max_value=1, format="%.3f"
            ),
            "account_age_signal": st.column_config.NumberColumn("Age Signal", format="%.3f"),
            "report_volume_signal": st.column_config.NumberColumn("Report Signal", format="%.3f"),
            "device_reuse_signal": st.column_config.NumberColumn("Device Signal", format="%.3f"),
            "ip_region_signal": st.column_config.NumberColumn("IP Signal", format="%.3f"),
            "toxicity_signal": st.column_config.NumberColumn("Toxicity Signal", format="%.3f"),
        },
    )
else:
    st.info("No signal scores found. Run scripts/generate_signal_scores.py.")

st.divider()

# ── Single-account lookup ────────────────────────────────────────────────
st.subheader("Look Up a Single Account")
account_id = st.text_input("Account ID", placeholder="e.g. ACC-000005")

if account_id:
    signal = repo.get_signal_for_account(account_id.strip())
    if signal is None:
        st.warning(f"No signal score found for '{account_id}'.")
    else:
        radar_labels = ["Account Age", "Report Volume", "Device Reuse", "IP Region", "Toxicity"]
        radar_values = [
            signal["account_age_signal"], signal["report_volume_signal"],
            signal["device_reuse_signal"], signal["ip_region_signal"],
            signal["toxicity_signal"],
        ]
        fig4 = go.Figure(go.Scatterpolar(
            r=radar_values + [radar_values[0]],
            theta=radar_labels + [radar_labels[0]],
            fill="toself", line_color="#4C6FFF",
        ))
        fig4.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            showlegend=False, margin=dict(l=20, r=20, t=20, b=20), height=400,
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            st.plotly_chart(fig4, use_container_width=True)
        with c2:
            st.metric("Composite Risk Score", f"{signal['composite_risk_score']:.3f}")
            st.write(f"**Computed at:** {signal['computed_at']}")
            for label, value in zip(radar_labels, radar_values):
                st.write(f"**{label}:** {value:.3f}")

st.divider()

# ── Live scoring: hypothetical account ───────────────────────────────────
# WIRING NOTE: everything above this line reads pre-computed scores from
# signal_repository.py (written once by scripts/generate_signal_scores.py).
# This section is different: it calls src/engines/signal_engine.py's
# SignalEngine LIVE, on demand, with values you type in -- the "Unified
# Signal Engine" module actually running as an engine, not just displaying
# a batch script's output.
st.subheader("Score a Hypothetical Account")
st.caption(
    "Runs the real Signal Engine live against these inputs, normalized "
    "against the current account population -- not a pre-computed lookup."
)

with st.form("hypothetical_account_form"):
    f1, f2, f3 = st.columns(3)
    with f1:
        h_created_at = st.date_input("Account created on")
        h_device_id = st.text_input("Device ID", placeholder="e.g. DEV-0018 (a reused device)")
    with f2:
        h_ip_region = st.text_input("IP region", placeholder="e.g. South-East-Asia")
        h_report_count = st.number_input("Report count", min_value=0, value=0, step=1)
    with f3:
        h_toxic_ratio = st.slider("Fraction of comments flagged toxic", 0.0, 1.0, 0.0, 0.05)

    submitted = st.form_submit_button("Score this account", type="primary")

if submitted:
    accounts_df = pd.read_csv(PROJECT_ROOT / "generated_data" / "accounts.csv", parse_dates=["created_at"])
    comments_df = pd.read_csv(PROJECT_ROOT / "generated_data" / "comments.csv")
    reports_df = pd.read_csv(PROJECT_ROOT / "generated_data" / "reports.csv")

    engine = SignalEngine()
    scored_population = engine.score_population(accounts_df, comments_df, reports_df)

    result = engine.score_hypothetical(
        created_at=h_created_at,
        device_id=h_device_id or "DEV-NONE",
        ip_region=h_ip_region or "Unknown",
        toxic_comment_ratio=h_toxic_ratio,
        report_count=int(h_report_count),
        population_accounts=scored_population,
    )

    st.success(f"Composite risk score: **{result['final_risk']:.3f}**")
    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Age", f"{result['account_age_signal']:.3f}")
    r2.metric("Reports", f"{result['report_volume_signal']:.3f}")
    r3.metric("Device", f"{result['device_reuse_signal']:.3f}")
    r4.metric("IP", f"{result['ip_region_signal']:.3f}")
    r5.metric("Toxicity", f"{result['toxicity_signal']:.3f}")