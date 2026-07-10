"""
tests/test_moderation_service.py
===================================
Covers the business-rule validation layer: allowed status transitions,
the evidence-before-resolve rule (checked against the real case_evidence
table), and the critical-priority escalation-before-resolution rule.

Every action here returns an ActionResult(ok, reason) rather than
raising for expected rejections -- these tests check .ok and .reason
directly, matching the real API.

Uses the isolated_db fixture -- every test runs against a throwaway
copy of the database, never the real one.
"""

from __future__ import annotations

from src.services.moderation_service import ModerationService, ActionResult
from src.repositories.moderator_repository import ModeratorRepository


def _get_repo_module(isolated_db):
    from src.repositories import moderator_repository as mod_repo_module
    return mod_repo_module


def test_assign_case_succeeds_for_valid_case_and_moderator(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    case_id = repo.get_queue(limit=1)[0]["case_id"]

    result = service.assign_case(case_id, "MOD-002")

    assert isinstance(result, ActionResult)
    assert result.ok is True


def test_assign_case_fails_for_unknown_case(isolated_db):
    service = ModerationService()
    result = service.assign_case("CASE-DOES-NOT-EXIST", "MOD-002")
    assert result.ok is False
    assert "no case found" in result.reason.lower()


def test_assign_case_fails_for_unknown_moderator(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    case_id = repo.get_queue(limit=1)[0]["case_id"]

    result = service.assign_case(case_id, "MOD-999-FAKE")
    assert result.ok is False
    assert "no moderator found" in result.reason.lower()


def test_change_status_rejects_invalid_status_string(isolated_db):
    import pytest

    service = ModerationService()
    repo = ModeratorRepository()
    case_id = repo.get_queue(limit=1)[0]["case_id"]

    with pytest.raises(ValueError):
        service.change_status(case_id, "not_a_real_status", "MOD-001")


def test_change_status_same_status_is_rejected(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    case = repo.get_queue(status="open", limit=1)[0]
    case_id = case["case_id"]

    result = service.change_status(case_id, "open", "MOD-001")
    assert result.ok is False
    assert "already" in result.reason.lower()


def test_closed_case_has_no_allowed_transitions(isolated_db):
    """closed is a terminal state in the real ALLOWED_TRANSITIONS map --
    reopening should be a deliberate new case, not a status flip."""
    service = ModerationService()
    repo = ModeratorRepository()
    mod_repo_module = _get_repo_module(isolated_db)

    case_id = repo.get_queue(limit=1)[0]["case_id"]

    conn = mod_repo_module.db.connect()
    conn.execute("UPDATE cases SET status = 'closed' WHERE case_id = ?", (case_id,))
    conn.commit()

    result = service.change_status(case_id, "in_progress", "MOD-001")
    assert result.ok is False
    assert "closed" in result.reason.lower()


def test_cannot_resolve_case_with_zero_evidence(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    mod_repo_module = _get_repo_module(isolated_db)

    queue = repo.get_queue(status="open", limit=1)
    case_id = queue[0]["case_id"]

    conn = mod_repo_module.db.connect()
    conn.execute("DELETE FROM case_evidence WHERE case_id = ?", (case_id,))
    conn.execute("UPDATE cases SET priority = 'medium', status = 'in_progress' WHERE case_id = ?", (case_id,))
    conn.commit()

    result = service.change_status(case_id, "resolved", "MOD-001")
    assert result.ok is False
    assert "evidence" in result.reason.lower()


def test_resolving_with_evidence_present_passes_the_evidence_rule(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    mod_repo_module = _get_repo_module(isolated_db)

    case_id = repo.get_queue(status="open", limit=1)[0]["case_id"]

    conn = mod_repo_module.db.connect()
    conn.execute(
        "INSERT INTO case_evidence (evidence_id, case_id, evidence_type, reference_id, added_at, added_by) "
        "VALUES ('EVID-TEST-001', ?, 'note', 'TEST-REF', datetime('now'), 'MOD-001')",
        (case_id,),
    )
    conn.execute("UPDATE cases SET priority = 'medium', status = 'in_progress' WHERE case_id = ?", (case_id,))
    conn.commit()

    result = service.change_status(case_id, "resolved", "MOD-001")
    assert result.ok is True


def test_critical_case_cannot_resolve_without_prior_escalation(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    mod_repo_module = _get_repo_module(isolated_db)

    case_id = repo.get_queue(limit=1)[0]["case_id"]

    conn = mod_repo_module.db.connect()
    conn.execute(
        "INSERT INTO case_evidence (evidence_id, case_id, evidence_type, reference_id, added_at, added_by) "
        "VALUES ('EVID-TEST-002', ?, 'note', 'TEST-REF', datetime('now'), 'MOD-001')",
        (case_id,),
    )
    conn.execute("UPDATE cases SET priority = 'critical', status = 'in_progress' WHERE case_id = ?", (case_id,))
    conn.execute("DELETE FROM case_timeline WHERE case_id = ? AND event_type = 'escalated'", (case_id,))
    conn.commit()

    result = service.change_status(case_id, "resolved", "MOD-001")
    assert result.ok is False
    assert "escalat" in result.reason.lower()


def test_critical_case_can_resolve_after_escalation(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    mod_repo_module = _get_repo_module(isolated_db)

    case_id = repo.get_queue(limit=1)[0]["case_id"]

    conn = mod_repo_module.db.connect()
    conn.execute(
        "INSERT INTO case_evidence (evidence_id, case_id, evidence_type, reference_id, added_at, added_by) "
        "VALUES ('EVID-TEST-003', ?, 'note', 'TEST-REF', datetime('now'), 'MOD-001')",
        (case_id,),
    )
    conn.execute("UPDATE cases SET priority = 'critical', status = 'escalated' WHERE case_id = ?", (case_id,))
    conn.commit()

    repo._write_timeline(conn, case_id, "escalated", "Escalated for test setup.")
    conn.commit()

    result = service.change_status(case_id, "resolved", "MOD-001")
    assert result.ok is True


def test_add_note_rejects_empty_text(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    case_id = repo.get_queue(limit=1)[0]["case_id"]

    result = service.add_note(case_id, "MOD-001", "   ")
    assert result.ok is False
    assert "empty" in result.reason.lower()


def test_add_note_succeeds_with_real_text(isolated_db):
    service = ModerationService()
    repo = ModeratorRepository()
    case_id = repo.get_queue(limit=1)[0]["case_id"]

    result = service.add_note(case_id, "MOD-001", "Real note text for testing.")
    assert result.ok is True

    notes = repo.get_notes(case_id)
    assert any(n["note_text"] == "Real note text for testing." for n in notes)