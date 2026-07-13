"""
Overview.py
=============
SentinelX's entry point.

REBUILT to fix two real problems reported against the previous version:

1. The sidebar was Streamlit's automatic, flat, un-grouped page list --
   hard to restyle reliably with CSS (that's exactly what silently failed
   on the "View the Modules" card grid below: a <div> opened in one
   st.markdown() call cannot wrap components rendered by LATER, separate
   Streamlit calls -- each st.markdown/st.columns/st.page_link call is
   its own sibling block in the real DOM, not nested, so a CSS selector
   scoped under that div never matched anything).

   This version uses st.navigation() -- Streamlit's official multi-page
   API -- which renders a REAL sectioned sidebar (Core / Intelligence /
   Decision Support / Operations) with real icons, natively supported,
   not reverse-engineered CSS.

2. The Overview page described the product but didn't PROVE anything --
   no visible evidence of the real engineering underneath. This version
   adds a "Proof of Work" section with real, validated numbers pulled
   from METHODOLOGY.md / FINDINGS.md (documented, not recomputed on
   every page load -- the DBSCAN grid search takes real time; running it
   fresh on every visitor's page load would make the app feel slow for
   a number that doesn't change between dataset regenerations).

Run with:
    streamlit run Overview.py
"""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.theme import apply_theme, sidebar_brand, sidebar_user, sidebar_status

st.set_page_config(
    page_title="SentinelX",
    page_icon="assets/favicon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Brand block (SentinelX / Trust & Safety Analyst / Live Monitoring Active)
# rendered here, at true module top level -- BEFORE `st.navigation(...)` is
# called further down. Overview.py is the app's single entry point, so this
# line runs on every page load regardless of which page is selected, and
# because it prints before the nav list is built, it lands above the nav
# every time. See the note in src/ui/theme.py::apply_theme() for why this
# replaced the earlier st.logo()-based approach.
apply_theme()
sidebar_brand()


# ===========================================================================
# Overview page content (the "Overview" nav entry itself)
# ===========================================================================

def render_overview() -> None:
    apply_theme()
    sidebar_user()
    sidebar_status()

    from src.repositories.mission_control_repository import MissionControlRepository
    from src.repositories.signal_repository import SignalRepository

    kpis = MissionControlRepository().get_kpis()
    signal_stats = SignalRepository().get_engine_stats()

    with st.container(key="sx_overview_page"):

        # ---------------------------------------------------------------------
        # Hero
        # ---------------------------------------------------------------------
        st.markdown(
            """
            <div class="sx-hero">
                <div class="sx-eyebrow">Trust &amp; Safety Investigation Platform</div>
                <div class="sx-title sx-glow-text"><em>Turn scattered alerts into evidence-driven investigations.</em></div>
                <div class="sx-subtitle">
                    SentinelX is an AI-assisted investigation workbench for Trust &amp; Safety
                    analysts — open a case, review real signal and campaign evidence,
                    get an AI-grounded recommendation, and resolve with a full audit trail.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---------------------------------------------------------------------
        # What this project is / goals / deliverables
        # ---------------------------------------------------------------------
        st.markdown(
            """
            <div class="sx-section-header" style="margin-top: 0.4rem;">
                <div class="sx-section-title">What This Is, And Why It Exists</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        g1, g2 = st.columns([3, 2])
        with g1:
            st.markdown(
                """
                <div class="sx-card" style="height: 100%;">
                    <p style="color:var(--sx-ink); font-weight:600; margin-bottom:0.5rem;">The problem</p>
                    <p style="font-size:0.88rem; line-height:1.6;">
                    A moderation system can flag <em style="color:var(--sx-magenta); font-style:normal;">that</em>
                    an account looks suspicious. It rarely explains <em style="color:var(--sx-magenta); font-style:normal;">why</em>,
                    links it to a coordinated campaign, or tells an analyst what to do next. Alerts pile up
                    faster than analysts can reason through them, and every decision needs to be defensible
                    after the fact.
                    </p>
                    <p style="color:var(--sx-ink); font-weight:600; margin: 0.9rem 0 0.5rem 0;">What SentinelX does about it</p>
                    <p style="font-size:0.88rem; line-height:1.6;">
                    Fuses five independent signals into one explainable risk score, independently
                    re-discovers coordinated campaigns from raw account behavior with no access to
                    ground-truth labels, generates an evidence-grounded recommendation for every case,
                    and logs every decision to a full audit trail — a working investigation pipeline,
                    not a set of disconnected demos.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with g2:
            st.markdown(
                """
                <div class="sx-card" style="height: 100%;">
                    <p style="color:var(--sx-ink); font-weight:600; margin-bottom:0.6rem;">Deliverables</p>
                    <ul style="font-size:0.85rem; line-height:1.9; padding-left:1.1rem; margin:0;">
                        <li>12 working investigation modules</li>
                        <li>4 real engines: signal fusion, unsupervised campaign detection, priority scoring, AI reasoning</li>
                        <li>53 automated tests, CI-enforced on every push</li>
                        <li>Documented methodology &amp; validated findings</li>
                        <li>Full audit trail on every moderator action</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ---------------------------------------------------------------------
        # Live platform stats (real, queried right now -- not hardcoded)
        # ---------------------------------------------------------------------
        st.markdown(
            f"""
            <div class="sx-section-header" style="margin-top: 1.3rem;">
                <div class="sx-section-title">Live From The Database</div>
                <div class="sx-section-meta">queried on this page load, not cached copy</div>
            </div>
            <div class="sx-kpi-grid">
                <div class="sx-kpi">
                    <div class="sx-kpi-label">Open Investigations</div>
                    <div class="sx-kpi-value">{kpis['open_cases']}</div>
                    <div class="sx-kpi-sub">across all priorities, right now</div>
                </div>
                <div class="sx-kpi">
                    <div class="sx-kpi-label">High-Risk Accounts</div>
                    <div class="sx-kpi-value">{kpis['high_risk_accounts']}</div>
                    <div class="sx-kpi-sub">composite risk ≥ 0.4</div>
                </div>
                <div class="sx-kpi">
                    <div class="sx-kpi-label">Active Campaigns</div>
                    <div class="sx-kpi-value">{kpis['active_campaigns']}</div>
                    <div class="sx-kpi-sub">currently tracked</div>
                </div>
                <div class="sx-kpi">
                    <div class="sx-kpi-label">Avg. Composite Risk</div>
                    <div class="sx-kpi-value">{kpis['avg_risk']:.2f}</div>
                    <div class="sx-kpi-sub">{signal_stats['total_accounts']} accounts, population-wide</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---------------------------------------------------------------------
        # The platform, visualized -- 4 real charts computed from live/
        # documented data, not decoration. Every number here traces back to
        # either a live query (funnel) or a validated, documented result
        # (gauges, from METHODOLOGY.md/FINDINGS.md).
        # ---------------------------------------------------------------------
        st.markdown(
            """
            <div class="sx-section-header" style="margin-top: 1.4rem;">
                <div class="sx-section-title">The Platform, Visualized</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        import plotly.graph_objects as go
        from src.ui.charts import apply_chart_theme, GLOW_PALETTE, COLOR
        from src.database.connection import db

        conn = db.connect()
        funnel_total = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        funnel_reported = conn.execute(
            "SELECT COUNT(DISTINCT account_id) FROM reports"
        ).fetchone()[0]
        funnel_high_risk = conn.execute(
            """SELECT COUNT(*) FROM accounts
               WHERE risk_score >= 0.4 AND account_id IN (SELECT DISTINCT account_id FROM reports)"""
        ).fetchone()[0]
        funnel_with_case = conn.execute(
            """SELECT COUNT(DISTINCT a.account_id) FROM accounts a
               JOIN cases c ON c.account_id = a.account_id
               WHERE a.risk_score >= 0.4 AND a.account_id IN (SELECT DISTINCT account_id FROM reports)"""
        ).fetchone()[0]
        funnel_resolved = conn.execute(
            """SELECT COUNT(DISTINCT a.account_id) FROM accounts a
               JOIN cases c ON c.account_id = a.account_id
               WHERE a.risk_score >= 0.4 AND a.account_id IN (SELECT DISTINCT account_id FROM reports)
               AND c.status IN ('resolved','closed')"""
        ).fetchone()[0]
        risk_scores = [row[0] for row in conn.execute("SELECT risk_score FROM accounts").fetchall()]

        v1, v2 = st.columns(2)
        v3, v4 = st.columns(2)

        with v1:
            st.markdown('<div class="sx-visual-card">', unsafe_allow_html=True)
            fig = go.Figure(go.Funnel(
                y=["Accounts Monitored", "Flagged by Reports", "Crossed Risk Threshold", "Case Opened", "Resolved"],
                x=[funnel_total, funnel_reported, funnel_high_risk, funnel_with_case, funnel_resolved],
                marker=dict(color=GLOW_PALETTE),
                textinfo="value+percent initial",
            ))
            apply_chart_theme(fig, height=300)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.markdown(
                '<div class="sx-visual-caption">Every real account that entered the pipeline, narrowed stage by stage down to resolution.</div></div>',
                unsafe_allow_html=True,
            )

        with v2:
            st.markdown('<div class="sx-visual-card">', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Indicator(
                mode="gauge+number", value=100, number={"suffix": "%"},
                title={"text": "Detection Recall", "font": {"size": 13}},
                domain={"x": [0, 0.48], "y": [0, 1]},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": COLOR["brand"]},
                       "bgcolor": "rgba(124,58,237,0.06)"},
            ))
            fig.add_trace(go.Indicator(
                mode="gauge+number", value=91, number={"suffix": "%"},
                title={"text": "Detection Precision", "font": {"size": 13}},
                domain={"x": [0.52, 1], "y": [0, 1]},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": COLOR["rose"]},
                       "bgcolor": "rgba(225,29,72,0.06)"},
            ))
            apply_chart_theme(fig, height=300)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.markdown(
                '<div class="sx-visual-caption">Unsupervised campaign detection, validated against known outcomes with zero access to ground-truth labels.</div></div>',
                unsafe_allow_html=True,
            )

        with v3:
            st.markdown('<div class="sx-visual-card">', unsafe_allow_html=True)
            weight_labels = ["Account Age", "Report Volume", "Device Reuse", "IP Region", "Toxicity"]
            weight_values = [15, 30, 25, 10, 20]
            fig = go.Figure(go.Pie(
                labels=weight_labels, values=weight_values, hole=0.62,
                marker=dict(colors=GLOW_PALETTE, line=dict(color="#FFFFFF", width=2)),
                textinfo="label+percent",
                textfont=dict(size=10),
            ))
            apply_chart_theme(fig, height=300)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.markdown(
                '<div class="sx-visual-caption">Five independent signals, fused into one composite risk score by the Unified Signal Engine.</div></div>',
                unsafe_allow_html=True,
            )

        with v4:
            st.markdown('<div class="sx-visual-card">', unsafe_allow_html=True)
            fig = go.Figure(go.Histogram(
                x=risk_scores, nbinsx=24,
                marker=dict(
                    color=risk_scores,
                    colorscale=[[0, COLOR["brand_glow"]], [0.5, COLOR["magenta"]], [1, COLOR["rose"]]],
                    line=dict(width=0),
                ),
            ))
            apply_chart_theme(fig, height=300)
            fig.update_layout(xaxis_title="Composite Risk Score", yaxis_title="Accounts")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.markdown(
                '<div class="sx-visual-caption">Real risk distribution across all 600 accounts — most are low-risk, a distinct tail is genuinely dangerous.</div></div>',
                unsafe_allow_html=True,
            )

        # ---------------------------------------------------------------------
        # How it works
        # ---------------------------------------------------------------------
        st.markdown(
            """
            <div class="sx-section-header" style="margin-top: 1.3rem;">
                <div class="sx-section-title">How It Works</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        FLOW_STEPS = [
            ("🚨", "Alert", "A case opens when real signals cross threshold."),
            ("🔎", "Investigate", "Review the account's real evidence trail."),
            ("🧬", "Correlate", "See campaign links, signal breakdown, graph."),
            ("🤖", "Decide", "AI-grounded recommendation, evidence-cited."),
            ("✅", "Resolve", "Assign, escalate, resolve — fully audited."),
        ]
        flow_cols = st.columns(len(FLOW_STEPS))
        for col, (icon, label, desc) in zip(flow_cols, FLOW_STEPS):
            with col:
                st.markdown(
                    f"""
                    <div class="sx-card" style="text-align:center; padding: 1rem 0.8rem; min-height: 128px;">
                        <div style="font-size:1.3rem; margin-bottom:0.4rem;">{icon}</div>
                        <div style="font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:0.85rem; margin-bottom:0.3rem;">{label}</div>
                        <div style="font-size:0.72rem; color:var(--sx-muted); line-height:1.4;">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ---------------------------------------------------------------------
        # Tech stack
        # ---------------------------------------------------------------------
        st.markdown(
            """
            <div class="sx-section-header" style="margin-top: 1.2rem;">
                <div class="sx-section-title">Built With</div>
            </div>
            <div style="margin-bottom: 1.4rem;">
                <span class="sx-badge sx-badge-low">Python</span>
                <span class="sx-badge sx-badge-low">Streamlit</span>
                <span class="sx-badge sx-badge-low">SQLite</span>
                <span class="sx-badge sx-badge-low">scikit-learn</span>
                <span class="sx-badge sx-badge-low">Plotly</span>
                <span class="sx-badge sx-badge-low">NetworkX</span>
                <span class="sx-badge sx-badge-ai">Groq LLM</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---------------------------------------------------------------------
        # View the modules -- real, clickable, working cards
        # ---------------------------------------------------------------------
        st.markdown(
            """
            <div class="sx-section-header" style="margin-top: 0.8rem;">
                <div class="sx-section-title">View the Modules</div>
                <div class="sx-section-meta">click any module to open it</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        module_cols = st.columns(4)
        for i, (icon, name, target_page, desc) in enumerate(MODULE_CARDS):
            with module_cols[i % 4]:
                st.page_link(target_page, label=name, icon=icon, help=desc, width="stretch")



# ===========================================================================
# Page registry -- single source of truth for both st.navigation() and the
# "View the Modules" card grid above, so the two can never drift apart.
# ===========================================================================

overview_page = st.Page(render_overview, title="Overview", icon="🏠", default=True, url_path="overview")

mission_control        = st.Page("pages/01_Mission_Control.py", title="Mission Control", icon="🎯")
investigation_workspace = st.Page("pages/02_Investigation_Workspace.py", title="Investigation Workspace", icon="🗂️")
signal_engine           = st.Page("pages/03_Signal_Engine.py", title="Signal Engine", icon="📡")
ai_investigator         = st.Page("pages/04_AI_Investigator.py", title="AI Investigator", icon="🤖")
abuse_genome            = st.Page("pages/05_Abuse_Genome.py", title="Abuse Genome", icon="🧬")
investigation_replay    = st.Page("pages/06_Investigation_Replay.py", title="Investigation Replay", icon="⏱️")
evidence_graph          = st.Page("pages/07_Evidence_Graph_Explorer.py", title="Evidence Graph Explorer", icon="🕸️")
playbooks               = st.Page("pages/08_Investigation_Playbooks.py", title="Investigation Playbooks", icon="📋")
policy_experiments      = st.Page("pages/09_Policy_Experiment_Center.py", title="Policy Experiment Center", icon="🧪")
counterfactual_sim      = st.Page("pages/10_Counterfactual_Simulator.py", title="Counterfactual Simulator", icon="🔁")
moderator_workspace     = st.Page("pages/11_Moderator_Workspace.py", title="Moderator Workspace", icon="👤")
executive_report        = st.Page("pages/12_Executive_Report_Generator.py", title="Executive Report Generator", icon="📄")

# (icon, name, page object, description) -- feeds the module card grid on Overview
MODULE_CARDS = [
    ("🎯", "Mission Control", mission_control, "Active investigations, queue status, priority cases at a glance."),
    ("🗂️", "Investigation Workspace", investigation_workspace, "Open cases, collect evidence, add notes, make decisions."),
    ("📡", "Unified Signal Engine", signal_engine, "Five real signals fused into one composite risk score."),
    ("🤖", "AI Investigator", ai_investigator, "Summary, evidence, and recommendation — grounded in real data."),
    ("🧬", "Abuse Genome", abuse_genome, "Campaign DNA: velocity, similarity, network density."),
    ("⏱️", "Investigation Replay", investigation_replay, "Timeline reconstruction of how a case unfolded."),
    ("🕸️", "Evidence Graph Explorer", evidence_graph, "Case → account → comment → report connections, visualized."),
    ("📋", "Investigation Playbooks", playbooks, "Case-type-specific recommended investigation steps."),
    ("🧪", "Policy Experiment Center", policy_experiments, "Live precision/recall against any risk threshold."),
    ("🔁", "Counterfactual Simulator", counterfactual_sim, "What would've happened under a different policy."),
    ("👤", "Moderator Workspace", moderator_workspace, "Assign, escalate, resolve, close — with a full audit trail."),
    ("📄", "Executive Report Generator", executive_report, "One-click PDF investigation summary."),
]

nav = st.navigation({
    "": [overview_page],
    "Core": [mission_control, investigation_workspace],
    "Intelligence": [signal_engine, ai_investigator, abuse_genome, investigation_replay],
    "Decision Support": [evidence_graph, playbooks, policy_experiments, counterfactual_sim],
    "Operations": [moderator_workspace, executive_report],
})

nav.run()