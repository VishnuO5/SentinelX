"""
pages/02_Investigation_Workspace.py
====================================
The core product screen: an analyst searches for an account, opens its
case, reviews evidence (comments, reports, signals, linked cases), and
adds an investigation note.

Search -> select -> review -> note. No hardcoded numbers -- everything
comes from InvestigationWorkspace, which reads the real database.
"""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.investigation_workspace import InvestigationWorkspace


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header, badge
apply_theme()
sidebar_user()
page_header("🗂️", "Investigation Workspace", "Search an account, review its real evidence, and log what you found.")

workspace = InvestigationWorkspace()

STATUS_KIND = {"active": "good", "flagged": "medium", "suspended": "critical", "banned": "critical"}

# ── Session state: which account is currently open ─────────────────────────
if "iw_selected_account" not in st.session_state:
    st.session_state.iw_selected_account = None


# ── Search / select panel ───────────────────────────────────────────────────
st.markdown(f'<div class="sx-card">{card_header("🔍", "Find an account")}', unsafe_allow_html=True)

search_col, _ = st.columns([2, 3])
with search_col:
    query = st.text_input(
        "Search by account ID or display name",
        placeholder="e.g. ACC-000005 or a display name",
        label_visibility="collapsed",
    )

results = workspace.search_accounts(query, limit=25)

if not results:
    st.info("No accounts match that search.")
else:
    options = {
        f"{r['account_id']} — {r['display_name']}  (risk {r['risk_score']:.2f}, {r['status']})": r["account_id"]
        for r in results
    }
    label = "Highest-risk accounts" if not query.strip() else f"Matches for '{query}'"
    st.caption(label)
    chosen_label = st.selectbox(label, options.keys(), label_visibility="collapsed")
    if st.button("Open case", type="primary"):
        st.session_state.iw_selected_account = options[chosen_label]
st.markdown("</div>", unsafe_allow_html=True)

# ── Case view ────────────────────────────────────────────────────────────────
account_id = st.session_state.iw_selected_account

if not account_id:
    st.info("Search for an account above and click **Open case** to begin.")
    st.stop()

case = workspace.open_case(account_id)

if "error" in case:
    st.error(case["error"])
    st.stop()

case_title = f"{case['account_id']} — {case['display_name']}"
st.markdown(f'<div class="sx-card">{card_header("🗎", case_title)}', unsafe_allow_html=True)
st.markdown(badge(case["status"], STATUS_KIND.get(case["status"], "low")), unsafe_allow_html=True)

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("Risk score", f"{case['risk_score']:.3f}")
kpi2.metric("Status", case["status"])
kpi3.metric("Campaign", case["campaign_id"] or "— none —")
kpi4.metric("Comments", case["total_comments"])
kpi5.metric("Reports", case["total_reports"])
st.markdown("</div>", unsafe_allow_html=True)

left, right = st.columns([2, 1])

with left:
    st.markdown(f'<div class="sx-card">{card_header("🧾", "Evidence")}', unsafe_allow_html=True)

    tab_comments, tab_reports, tab_cases = st.tabs(
        ["Comments", "Reports", f"Cases ({case['total_cases']})"]
    )

    with tab_comments:
        if case["latest_comments"]:
            st.dataframe(
                [
                    {
                        "posted_at": c["posted_at"],
                        "toxicity_label": c["toxicity_label"],
                        "toxicity_score": c["toxicity_score"],
                        "text": c["text"][:200],
                    }
                    for c in case["latest_comments"]
                ],
                width="stretch",
            )
        else:
            st.info("No comments on record for this account.")

    with tab_reports:
        if case["latest_reports"]:
            st.dataframe(
                [
                    {
                        "reported_at": r["reported_at"],
                        "report_reason": r["report_reason"],
                        "reporter_type": r["reporter_type"],
                    }
                    for r in case["latest_reports"]
                ],
                width="stretch",
            )
        else:
            st.info("No reports on record for this account.")

    with tab_cases:
        if case["cases"]:
            st.dataframe(
                [
                    {
                        "case_id": c["case_id"],
                        "case_type": c["case_type"],
                        "priority": c["priority"],
                        "status": c["status"],
                        "opened_at": c["opened_at"],
                        "resolved_at": c["resolved_at"],
                        "assigned_moderator_id": c["assigned_moderator_id"],
                    }
                    for c in case["cases"]
                ],
                width="stretch",
            )
        else:
            st.info("No cases have been opened for this account yet.")
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown(f'<div class="sx-card">{card_header("📡", "Unified Signal Engine")}', unsafe_allow_html=True)
    if case["signals"]:
        s = case["signals"]
        st.metric("Composite risk", f"{s['final_risk']:.3f}")
        st.progress(min(s["account_age"], 1.0), text=f"Account age signal — {s['account_age']:.2f}")
        st.progress(min(s["report_volume"], 1.0), text=f"Report volume signal — {s['report_volume']:.2f}")
        st.progress(min(s["device_reuse"], 1.0), text=f"Device reuse signal — {s['device_reuse']:.2f}")
        st.progress(min(s["ip_region"], 1.0), text=f"IP region signal — {s['ip_region']:.2f}")
        st.progress(min(s["toxicity"], 1.0), text=f"Toxicity signal — {s['toxicity']:.2f}")
    else:
        st.info("No signal score computed for this account yet.")
    st.markdown("</div>", unsafe_allow_html=True)

# ── Investigation notes ─────────────────────────────────────────────────────
st.markdown(f'<div class="sx-card">{card_header("📝", "Investigation notes")}', unsafe_allow_html=True)

if not case["cases"]:
    st.info("Notes can only be added to a case. This account has no open case yet.")
else:
    if case["notes"]:
        for n in case["notes"]:
            with st.container(border=True):
                st.markdown(f"**{n['moderator_name'] or n['moderator_id']}** — {n['created_at']}")
                st.write(n["note_text"])
    else:
        st.caption("No notes yet on this account's case(s).")

    st.markdown("#### Add a note")

    case_options = {c["case_id"]: c["case_id"] for c in case["cases"]}
    selected_case_id = st.selectbox("Case", case_options.keys())

    moderators = workspace.list_moderators()
    mod_options = {f"{m['name']} ({m['role']})": m["moderator_id"] for m in moderators}
    selected_mod_label = st.selectbox("Note author", mod_options.keys())

    note_text = st.text_area("Note", placeholder="What did you find? What's the next step?")

    if st.button("Add note"):
        if not note_text.strip():
            st.warning("Write something before adding the note.")
        else:
            workspace.add_note(
                case_id=selected_case_id,
                moderator_id=mod_options[selected_mod_label],
                note_text=note_text,
            )
            st.success("Note added.")
            st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()