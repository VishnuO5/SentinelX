"""
pages/05_Abuse_Genome.py
==========================
Abuse Genome -- Campaign DNA visualization. Every campaign gets a
4-dimension "DNA profile": velocity, similarity, network density, and
report volume. This is the branding/memorable feature called out in the
project brief.

All four numbers are real: velocity/similarity/network_density come from
scripts/generate_campaigns.py + compute_campaign_similarity.py (real
TF-IDF cosine similarity, not a random placeholder), and report volume is
computed live from actual reports against the campaign's real accounts.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.campaign_repository import CampaignRepository
from src.engines.campaign_engine import CampaignEngine, FEATURE_COLUMNS


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("🧬", "Abuse Genome", "Campaign DNA: velocity, similarity, network density, and report volume, side by side.")

repo = CampaignRepository()
campaigns = repo.list_campaigns()

if not campaigns:
    st.info("No campaigns found. Run the generator pipeline first.")
    st.stop()

# ── Overview: all campaigns compared ──────────────────────────────────────
st.markdown(f'<div class="sx-card">{card_header("🧬", "All campaigns")}', unsafe_allow_html=True)

overview_rows = []
for c in campaigns:
    dna = repo.get_campaign_dna(c["campaign_id"])
    overview_rows.append({
        "Campaign": c["campaign_id"],
        "Type": c["campaign_type"],
        "Status": c["status"],
        "Accounts": c["account_count"],
        "Velocity": dna["velocity"],
        "Similarity": dna["similarity"],
        "Network Density": dna["network_density"],
        "Reports": dna["report_count"],
    })

st.dataframe(
    overview_rows,
    width="stretch",
    column_config={
        "Velocity": st.column_config.ProgressColumn("Velocity", min_value=0, max_value=1, format="%.2f"),
        "Similarity": st.column_config.ProgressColumn("Similarity", min_value=0, max_value=1, format="%.3f"),
        "Network Density": st.column_config.ProgressColumn("Network Density", min_value=0, max_value=1, format="%.2f"),
    },
)
st.markdown("</div>", unsafe_allow_html=True)

# ── Compare campaign types ──────────────────────────────────────────────
st.markdown(f'<div class="sx-card">{card_header("🐾", "DNA by campaign type")}', unsafe_allow_html=True)
st.caption("Average signature per abuse type -- this is what should differentiate a bot network from a harassment campaign.")

by_type: dict[str, list] = {}
for c in campaigns:
    dna = repo.get_campaign_dna(c["campaign_id"])
    by_type.setdefault(c["campaign_type"], []).append(dna)

fig_compare = go.Figure()
dims = ["velocity", "similarity", "network_density", "report_volume_normalized"]
dim_labels = ["Velocity", "Similarity", "Network Density", "Report Volume"]

for campaign_type, dna_list in by_type.items():
    avg_values = [sum(d[dim] for d in dna_list) / len(dna_list) for dim in dims]
    fig_compare.add_trace(go.Scatterpolar(
        r=avg_values + [avg_values[0]],
        theta=dim_labels + [dim_labels[0]],
        name=campaign_type,
        fill="toself",
        opacity=0.5,
    ))

fig_compare.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    height=500, margin=dict(l=20, r=20, t=20, b=20),
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color=theme.CHART_NEUTRAL),
)
st.plotly_chart(fig_compare, width="stretch")
st.markdown("</div>", unsafe_allow_html=True)

# ── Single campaign deep dive ─────────────────────────────────────────────
st.markdown(f'<div class="sx-card">{card_header("🔬", "Campaign deep dive")}', unsafe_allow_html=True)

campaign_ids = [c["campaign_id"] for c in campaigns]
selected = st.selectbox("Select a campaign", options=campaign_ids)

if selected:
    dna = repo.get_campaign_dna(selected)
    accounts = repo.get_campaign_accounts(selected)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Velocity", f"{dna['velocity']:.2f}")
    c2.metric("Similarity", f"{dna['similarity']:.3f}")
    c3.metric("Network Density", f"{dna['network_density']:.2f}")
    c4.metric("Reports", dna["report_count"])

    left, right = st.columns([1, 1])

    with left:
        fig_dna = go.Figure(go.Scatterpolar(
            r=[dna["velocity"], dna["similarity"], dna["network_density"],
               dna["report_volume_normalized"], dna["velocity"]],
            theta=dim_labels + [dim_labels[0]],
            fill="toself", line_color=theme.CHART_SECONDARY,
        ))
        fig_dna.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            showlegend=False, height=350, margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=theme.CHART_NEUTRAL),
        )
        st.plotly_chart(fig_dna, width="stretch")

    with right:
        st.write(f"**Type:** {dna['campaign_type']}")
        st.write(f"**Status:** {dna['status']}")
        st.write(f"**Member accounts:** {dna['account_count']}")
        st.write(f"**Total reports across all members:** {dna['report_count']}")

    st.markdown(f"#### Accounts in {selected}")
    if accounts:
        st.dataframe(accounts, width="stretch")
    else:
        st.info("No accounts linked to this campaign.")
st.markdown("</div>", unsafe_allow_html=True)

# ── Independent detection validation ─────────────────────────────────────
# WIRING NOTE: everything above reads campaign_id assignments that were
# fixed at data-generation time. This section is different: it runs
# src/engines/campaign_engine.py's CampaignEngine LIVE, with NO knowledge
# of those campaign_id labels, and only afterward checks how many of its
# independently-discovered clusters actually match them -- the same way
# you'd validate a real anomaly-detection system against held-out ground
# truth, not just display pre-labeled data.
st.markdown(f'<div class="sx-card">{card_header("✅", "Independent detection validation")}', unsafe_allow_html=True)
st.caption(
    "Runs unsupervised DBSCAN clustering over raw account signals "
    "(device reuse, account age, report volume, toxicity, comment-text "
    "similarity) with zero access to the real campaign_id column, then "
    "checks how many of the known coordinated accounts it found on its own."
)

if st.button("Run independent campaign detection"):
    with st.spinner("Clustering accounts from raw signals (tuning DBSCAN)..."):
        accounts_df = pd.read_csv(PROJECT_ROOT / "generated_data" / "accounts.csv", parse_dates=["created_at"])
        comments_df = pd.read_csv(PROJECT_ROOT / "generated_data" / "comments.csv")
        reports_df = pd.read_csv(PROJECT_ROOT / "generated_data" / "reports.csv")

        engine = CampaignEngine()
        labeled, metrics = engine.run_full_pipeline(accounts_df, comments_df, reports_df)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recall", f"{metrics['recall']:.1%}")
    m2.metric("Precision", f"{metrics['precision']:.1%}")
    m3.metric("False Positive Rate", f"{metrics['false_positive_rate']:.1%}")
    m4.metric("Clusters Found", metrics["clusters_found"])

    st.caption(
        f"Tuned parameters: eps={metrics['eps']}, min_samples={metrics['min_samples']} "
        f"-- {metrics['true_positives']} of {metrics['true_positives'] + metrics['false_negatives']} "
        f"real coordinated accounts recovered from raw signals alone, "
        f"{metrics['false_positives']} false positives out of "
        f"{metrics['false_positives'] + metrics['true_negatives']} organic accounts."
    )

    # ── PCA scatter: the recall/precision numbers above, made visible ───
    # The 5 raw signal features DBSCAN clustered on (device reuse, account
    # age, report volume, toxicity, text similarity) are reduced to 2D via
    # PCA purely for plotting -- the clustering itself already happened
    # above, in the real 5-dimensional space. Each point is colored by
    # where it lands in the confusion matrix (flagged vs. real campaign
    # membership), so the 100%/91.5%-style numbers are something you can
    # actually see, not just read in a table.
    st.markdown("#### What the detector actually found")
    st.caption(
        "Each dot is one account, projected from the real 5-signal feature "
        "space down to 2D for plotting. Color shows whether the detector's "
        "call agreed with the real campaign label."
    )

    X = StandardScaler().fit_transform(labeled[FEATURE_COLUMNS])
    coords = PCA(n_components=2, random_state=42).fit_transform(X)

    is_true_campaign = labeled["campaign_id"].notna().values
    is_flagged = labeled["flagged"].values

    category = pd.Series(
        [
            "True positive (flagged, real campaign)" if f and t else
            "False positive (flagged, not a campaign)" if f and not t else
            "False negative (missed, real campaign)" if not f and t else
            "True negative (not flagged, organic)"
            for f, t in zip(is_flagged, is_true_campaign)
        ]
    )
    CATEGORY_COLORS = {
        "True positive (flagged, real campaign)": theme.CHART_ACCENT_TEAL,
        "False positive (flagged, not a campaign)": theme.CHART_SECONDARY,
        "False negative (missed, real campaign)": theme.CHART_ACCENT_AMBER,
        "True negative (not flagged, organic)": theme.CHART_NEUTRAL,
    }

    fig_scatter = go.Figure()
    for cat, color in CATEGORY_COLORS.items():
        mask = category == cat
        if mask.sum() == 0:
            continue
        fig_scatter.add_trace(go.Scatter(
            x=coords[mask.values, 0], y=coords[mask.values, 1],
            mode="markers", name=cat,
            marker=dict(size=7, color=color, opacity=0.75, line=dict(width=0)),
            hovertext=labeled.loc[mask.values, "account_id"],
            hoverinfo="text",
        ))
    fig_scatter.update_layout(
        height=460, margin=dict(l=20, r=20, t=10, b=20),
        xaxis_title="PCA component 1", yaxis_title="PCA component 2",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme.CHART_NEUTRAL),
        legend=dict(orientation="h", y=-0.18),
    )
    st.plotly_chart(fig_scatter, width="stretch")
st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()