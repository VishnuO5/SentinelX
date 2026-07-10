"""
src/services/investigation_workspace.py
=======================================
Investigation Workspace Service.

Transforms the raw repository bundle into a clean dict that dashboard
pages can consume directly without knowing about DB column names.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.investigation_repository import InvestigationRepository


class InvestigationWorkspace:

    def __init__(self):
        self.repository = InvestigationRepository()

    def open_case(self, account_id: str) -> dict:
        data = self.repository.load_case(account_id)

        account  = data["account"]
        signals  = data["signals"]
        reports  = data["reports"]
        comments = data["comments"]
        cases    = data["cases"]
        evidence = data["evidence"]
        notes    = data["notes"]

        if account is None:
            return {"error": f"Account '{account_id}' not found."}

        # Map actual signal_scores column names (see scripts/init_db.py --
        # the approved schema calls the composite column
        # "composite_risk_score". It's no longer "final_risk": that name
        # only existed in the DB because data_loader.py used to rebuild
        # the table around whatever generate_signal_scores.py's CSV
        # happened to call it. data_loader.py now renames it on load, so
        # the DB (and this code) match the schema doc again.)
        signal_block = None
        if signals:
            signal_block = {
                "account_age"   : signals["account_age_signal"],
                "report_volume" : signals["report_volume_signal"],
                "device_reuse"  : signals["device_reuse_signal"],
                "ip_region"     : signals["ip_region_signal"],
                "toxicity"      : signals["toxicity_signal"],
                "final_risk"    : signals["composite_risk_score"],
            }

        return {
            "account_id"     : account["account_id"],
            "display_name"   : account["display_name"],
            "status"         : account["status"],
            "risk_score"     : account["risk_score"],
            "campaign_id"    : account["campaign_id"],
            "total_comments" : len(comments),
            "total_reports"  : len(reports),
            "total_cases"    : len(cases),
            "total_evidence" : len(evidence),
            "signals"        : signal_block,
            "latest_comments": comments[:10],
            "latest_reports" : reports[:10],
            "cases"          : cases,
            "evidence"       : evidence,
            "notes"          : notes,
        }

    def search_accounts(self, query: str = "", limit: int = 25) -> list:
        """Used by the page's search box. Empty query -> highest-risk
        accounts first, so there's something useful to show by default."""
        return self.repository.search_accounts(query, limit=limit)

    def list_moderators(self) -> list:
        """Used to populate the 'note author' dropdown on the page."""
        return self.repository.list_moderators()

    def add_note(self, case_id: str, moderator_id: str, note_text: str) -> str:
        note_text = (note_text or "").strip()
        if not note_text:
            raise ValueError("Note text cannot be empty.")
        return self.repository.add_case_note(case_id, moderator_id, note_text)


if __name__ == "__main__":
    workspace = InvestigationWorkspace()
    case = workspace.open_case("ACC-000005")
    if "error" in case:
        print("ERROR:", case["error"])
    else:
        print(f"Account  : {case['account_id']} — {case['display_name']}")
        print(f"Risk     : {case['risk_score']}")
        print(f"Comments : {case['total_comments']}")
        print(f"Reports  : {case['total_reports']}")
        print(f"Cases    : {case['total_cases']}")
        if case["signals"]:
            print(f"Signals  : {case['signals']}")