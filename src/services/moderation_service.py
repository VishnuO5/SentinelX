"""
src/services/moderation_service.py
=====================================
Business-rule validation sitting above ModeratorRepository. The
repository itself will happily let you jump a case from "closed" back to
"escalated," resolve a case with zero evidence attached, or resolve a
critical-priority case without ever escalating it -- it just executes
whatever SQL it's given. Those are real process rules a T&S team would
actually enforce, and they belong here, not silently inside raw SQL.

Every action returns a small result object rather than raising for
"expected" rejections (case not found, invalid transition) -- pages can
show the reason directly instead of catching exceptions. Programming
errors (unknown status string) still raise, same as the repository.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db
from src.repositories.moderator_repository import ModeratorRepository, VALID_STATUSES

# Explicit allowed transitions. Anything not listed here is rejected.
# "closed" has no outgoing transitions -- a closed case is genuinely done;
# reopening one should be a deliberate new case, not a status flip.
ALLOWED_TRANSITIONS = {
    "open": {"in_progress", "escalated", "resolved", "closed"},
    "in_progress": {"escalated", "resolved", "closed"},
    "escalated": {"resolved", "closed"},
    "resolved": {"closed", "escalated"},  # resolved -> escalated covers "resolution didn't hold"
    "closed": set(),
}

CRITICAL_PRIORITIES_REQUIRING_ESCALATION = {"critical"}


@dataclass
class ActionResult:
    ok: bool
    reason: str = ""


class ModerationService:

    def __init__(self, repo: ModeratorRepository | None = None):
        self.repo = repo or ModeratorRepository()

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _get_evidence_count(self, case_id: str) -> int:
        conn = db.connect()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM case_evidence WHERE case_id = ?", (case_id,)
        ).fetchone()
        return row["n"] if row else 0

    def _has_been_escalated(self, case_id: str) -> bool:
        conn = db.connect()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM case_timeline WHERE case_id = ? AND event_type = 'escalated'",
            (case_id,),
        ).fetchone()
        return (row["n"] if row else 0) > 0

    # ------------------------------------------------------------------
    # validated actions
    # ------------------------------------------------------------------

    def assign_case(self, case_id: str, moderator_id: str) -> ActionResult:
        case = self.repo.get_case_summary(case_id)
        if case is None:
            return ActionResult(False, f"No case found with ID '{case_id}'.")

        moderators = {m["moderator_id"] for m in self.repo.list_moderators()}
        if moderator_id not in moderators:
            return ActionResult(False, f"No moderator found with ID '{moderator_id}'.")

        self.repo.assign_case(case_id, moderator_id)
        return ActionResult(True)

    def change_status(self, case_id: str, new_status: str, moderator_id: str) -> ActionResult:
        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")

        case = self.repo.get_case_summary(case_id)
        if case is None:
            return ActionResult(False, f"No case found with ID '{case_id}'.")

        current_status = case["status"]

        if new_status == current_status:
            return ActionResult(False, f"Case is already '{current_status}'.")

        if new_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
            return ActionResult(
                False,
                f"Cannot move a case from '{current_status}' to '{new_status}'. "
                f"Allowed next steps: {sorted(ALLOWED_TRANSITIONS.get(current_status, set())) or 'none'}.",
            )

        if new_status == "resolved":
            evidence_count = self._get_evidence_count(case_id)
            if evidence_count == 0:
                return ActionResult(
                    False,
                    "Cannot resolve a case with no evidence attached. "
                    "Add evidence via the Evidence Graph Explorer first.",
                )

            if case["priority"] in CRITICAL_PRIORITIES_REQUIRING_ESCALATION and not self._has_been_escalated(case_id):
                return ActionResult(
                    False,
                    "Critical-priority cases must be escalated for senior review "
                    "before they can be resolved.",
                )

        self.repo.update_status(case_id, new_status, moderator_id)
        return ActionResult(True)

    def add_note(self, case_id: str, moderator_id: str, note_text: str) -> ActionResult:
        case = self.repo.get_case_summary(case_id)
        if case is None:
            return ActionResult(False, f"No case found with ID '{case_id}'.")

        if not note_text or not note_text.strip():
            return ActionResult(False, "Note text cannot be empty.")

        self.repo.add_note(case_id, moderator_id, note_text.strip())
        return ActionResult(True)