"""
pages/11_Moderator_Workspace.py
=================================
Where investigations resolve: assign a case to a moderator, escalate,
resolve, or close it -- each action writes a real audit_log entry and
case_timeline event, and add-note writes a real case_notes row.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.moderator_repository import ModeratorRepository, VALID_STATUSES
from src.services.moderation_service import ModerationService, ALLOWED_TRANSITIONS


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("🛡️", "Moderator Workspace", "Assign, escalate, resolve, and close investigations. Every action is logged.")

repo = ModeratorRepository()
service = ModerationService(repo)

moderators = repo.list_moderators()
mod_lookup = {m["moderator_id"]: m["name"] for m in moderators}

st.markdown(f'<div class="sx-card">{card_header("🧑‍💼", "Moderator workload")}', unsafe_allow_html=True)
st.dataframe(moderators, width="stretch", hide_index=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(f'<div class="sx-card">{card_header("🗃️", "Case queue")}', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    filter_moderator = st.selectbox(
        "Filter by moderator",
        ["All"] + [f"{m['moderator_id']} — {m['name']}" for m in moderators],
    )
with col2:
    filter_status = st.selectbox("Filter by status", ["All"] + VALID_STATUSES)

moderator_id_filter = None
if filter_moderator != "All":
    moderator_id_filter = filter_moderator.split(" — ")[0]

status_filter = None if filter_status == "All" else filter_status

queue = repo.get_queue(moderator_id=moderator_id_filter, status=status_filter, limit=100)

st.caption(f"{len(queue)} case(s) match this filter.")

if not queue:
    st.info("No cases match this filter.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

case_options = {
    f"{c['case_id']} — {c['case_type']} ({c['priority']}, {c['status']}) — "
    f"{c['moderator_name'] or 'unassigned'}": c["case_id"]
    for c in queue
}
selected_label = st.selectbox("Open a case", list(case_options.keys()))
selected_case_id = case_options[selected_label]
st.markdown("</div>", unsafe_allow_html=True)

summary = repo.get_case_summary(selected_case_id)

st.markdown(f'<div class="sx-card">{card_header("📌", "Case detail & actions")}', unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Status", summary["status"])
col2.metric("Priority", summary["priority"])
col3.metric("Account Risk", f"{summary['risk_score']:.3f}" if summary.get("risk_score") is not None else "—")
col4.metric("Assigned To", summary.get("moderator_name") or "Unassigned")

st.markdown(f"**Account:** {summary.get('display_name')} ({summary['account_id']}) — "
            f"status: {summary.get('account_status')}")

action_col1, action_col2 = st.columns(2)

with action_col1:
    st.markdown("**Assign / Reassign**")
    assign_choice = st.selectbox(
        "Assign to",
        [f"{m['moderator_id']} — {m['name']}" for m in moderators],
        key="assign_select",
    )
    if st.button("Assign Case"):
        mod_id = assign_choice.split(" — ")[0]
        result = service.assign_case(selected_case_id, mod_id)
        if result.ok:
            st.success(f"Assigned to {mod_lookup.get(mod_id, mod_id)}.")
            st.rerun()
        else:
            st.error(result.reason)

with action_col2:
    st.markdown("**Change Status**")
    acting_moderator = st.selectbox(
        "Acting as",
        [f"{m['moderator_id']} — {m['name']}" for m in moderators],
        key="acting_select",
    )
    acting_mod_id = acting_moderator.split(" — ")[0]

    status_btn_cols = st.columns(4)
    labels = ["In Progress", "Escalate", "Resolve", "Close"]
    targets = ["in_progress", "escalated", "resolved", "closed"]
    allowed_next = ALLOWED_TRANSITIONS.get(summary["status"], set())
    for btn_col, label, target in zip(status_btn_cols, labels, targets):
        disabled = target not in allowed_next
        if btn_col.button(label, key=f"status_{target}", disabled=disabled):
            result = service.change_status(selected_case_id, target, acting_mod_id)
            if result.ok:
                st.success(f"Case marked {target}.")
                st.rerun()
            else:
                st.error(result.reason)
    if not allowed_next:
        st.caption("This case is closed — no further status changes are allowed.")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(f'<div class="sx-card">{card_header("📝", "Case notes")}', unsafe_allow_html=True)
note_moderator = st.selectbox(
    "Note author",
    [f"{m['moderator_id']} — {m['name']}" for m in moderators],
    key="note_author",
)
note_text = st.text_area("Add a note")
if st.button("Add Note"):
    mod_id = note_moderator.split(" — ")[0]
    result = service.add_note(selected_case_id, mod_id, note_text)
    if result.ok:
        st.success("Note added.")
        st.rerun()
    else:
        st.warning(result.reason)

notes = repo.get_notes(selected_case_id)
if notes:
    for n in notes:
        st.markdown(f"**{n.get('moderator_name') or n['moderator_id']}** — {n['created_at']}")
        st.write(n["note_text"])
        st.markdown("---")
else:
    st.caption("No notes yet.")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(f'<div class="sx-card">{card_header("🕵️", "Audit trail")}', unsafe_allow_html=True)
audit = repo.get_audit_log(selected_case_id)
if audit:
    # Timeline visual, oldest -> newest left to right, so a case's
    # lifecycle (assign -> in_progress -> escalated -> resolved, etc.)
    # reads at a glance instead of only as a raw log table.
    timeline_events = list(reversed(audit))  # get_audit_log() comes back newest-first
    ACTION_COLOR_KEYS = [
        ("resolved", theme.CHART_ACCENT_TEAL),
        ("closed", theme.CHART_NEUTRAL),
        ("escalat", theme.CHART_SECONDARY),
        ("assigned", theme.CHART_PRIMARY),
        ("note", theme.CHART_TERTIARY),
        ("status changed", theme.CHART_ACCENT_AMBER),
    ]
    def _color_for(action: str) -> str:
        action_l = action.lower()
        for key, color in ACTION_COLOR_KEYS:
            if key in action_l:
                return color
        return theme.CHART_NEUTRAL

    x_labels = [f"{i+1}" for i in range(len(timeline_events))]
    colors = [_color_for(a["action"]) for a in timeline_events]
    hover = [f"{a['action']}<br>{a.get('moderator_name') or a['moderator_id']}<br>{a['timestamp']}" for a in timeline_events]

    tfig = go.Figure()
    tfig.add_trace(go.Scatter(
        x=x_labels, y=[0] * len(x_labels), mode="markers+lines",
        marker=dict(size=18, color=colors, line=dict(width=2, color="rgba(255,255,255,0.6)")),
        line=dict(color="rgba(148,163,184,0.4)", width=2),
        hovertext=hover, hoverinfo="text",
    ))
    tfig.update_layout(
        height=140, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[-1, 1]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(tfig, width='stretch')
    st.caption("Hover a point for the action, moderator, and timestamp. Left = earliest, right = most recent.")

    st.dataframe(
        [{"Timestamp": a["timestamp"], "Moderator": a.get("moderator_name") or a["moderator_id"],
          "Action": a["action"]} for a in audit],
        width="stretch", hide_index=True,
    )
else:
    st.caption("No audit events yet for this case.")
st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()