"""
src/repositories/evidence_repository.py
==========================================
Real queries backing the Evidence Graph Explorer: builds a small
Case -> Account -> Comments/Reports/Campaign graph from actual
case_evidence rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class EvidenceRepository:

    def list_cases_with_evidence(self, limit: int = 100) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT DISTINCT c.case_id, c.case_type, c.priority, c.account_id
            FROM case_evidence e
            JOIN cases c ON e.case_id = c.case_id
            ORDER BY c.opened_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_evidence_graph_data(self, case_id: str) -> dict | None:
        """Returns nodes + edges for the Case -> Account -> Evidence graph."""
        conn = db.connect()

        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if case is None:
            return None
        case = dict(case)

        account = conn.execute(
            "SELECT * FROM accounts WHERE account_id = ?", (case["account_id"],)
        ).fetchone()
        account = dict(account) if account else {}

        evidence_rows = conn.execute(
            "SELECT * FROM case_evidence WHERE case_id = ?", (case_id,)
        ).fetchall()
        evidence_rows = [dict(r) for r in evidence_rows]

        nodes = []
        edges = []

        case_node = f"case::{case['case_id']}"
        account_node = f"account::{account.get('account_id', 'unknown')}"

        nodes.append({"id": case_node, "label": case["case_id"], "type": "case"})
        nodes.append({"id": account_node, "label": account.get("account_id", "?"), "type": "account"})
        edges.append({"source": case_node, "target": account_node, "label": "concerns"})

        for e in evidence_rows:
            etype = e["evidence_type"]
            ref = e["reference_id"]
            node_id = f"{etype}::{ref}"

            if etype == "comment":
                comment = conn.execute(
                    "SELECT toxicity_label, toxicity_score FROM comments WHERE comment_id = ?", (ref,)
                ).fetchone()
                label = f"{ref}\n({comment['toxicity_label']})" if comment else ref
            elif etype == "report":
                report = conn.execute(
                    "SELECT report_reason FROM reports WHERE report_id = ?", (ref,)
                ).fetchone()
                label = f"{ref}\n({report['report_reason']})" if report else ref
            elif etype == "campaign":
                label = ref
            else:
                label = ref

            nodes.append({"id": node_id, "label": label, "type": etype})
            edges.append({"source": account_node, "target": node_id, "label": etype})

        return {"case": case, "account": account, "nodes": nodes, "edges": edges}