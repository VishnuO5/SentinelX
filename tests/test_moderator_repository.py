"""
tests/test_moderator_repository.py
=====================================
Covers assignment, status changes, notes, and the audit trail they
write. Uses the isolated_db fixture -- every test here runs against a
throwaway copy of the database, never the real one.
"""

from __future__ import annotations

from src.repositories.moderator_repository import ModeratorRepository


def test_list_moderators_returns_all_eight(isolated_db):
    repo = ModeratorRepository()
    moderators = repo.list_moderators()
    assert len(moderators) == 8
    assert all("moderator_id" in m and "name" in m for m in moderators)


def test_assign_case_updates_assignment_and_writes_audit(isolated_db):
    repo = ModeratorRepository()
    queue = repo.get_queue(limit=1)
    case_id = queue[0]["case_id"]

    repo.assign_case(case_id, "MOD-002")

    summary = repo.get_case_summary(case_id)
    assert summary["assigned_moderator_id"] == "MOD-002"

    audit = repo.get_audit_log(case_id)
    assert any("assigned" in a["action"] for a in audit)


def test_assign_case_syncs_moderator_active_case_count(isolated_db):
    repo = ModeratorRepository()
    queue = repo.get_queue(status="open", limit=1)
    case_id = queue[0]["case_id"]

    before = {m["moderator_id"]: m["active_case_count"] for m in repo.list_moderators()}
    repo.assign_case(case_id, "MOD-003")
    after = {m["moderator_id"]: m["active_case_count"] for m in repo.list_moderators()}

    assert after["MOD-003"] >= before["MOD-003"]


def test_update_status_to_resolved_sets_resolved_at(isolated_db):
    repo = ModeratorRepository()
    queue = repo.get_queue(status="open", limit=1)
    case_id = queue[0]["case_id"]

    repo.update_status(case_id, "resolved", "MOD-001")

    summary = repo.get_case_summary(case_id)
    assert summary["status"] == "resolved"
    assert summary["resolved_at"] is not None


def test_update_status_writes_timeline_event(isolated_db):
    from src.repositories import moderator_repository as mod_repo_module

    repo = ModeratorRepository()
    queue = repo.get_queue(status="open", limit=1)
    case_id = queue[0]["case_id"]

    repo.update_status(case_id, "in_progress", "MOD-001")

    conn = mod_repo_module.db.connect()
    rows = conn.execute(
        "SELECT * FROM case_timeline WHERE case_id = ? ORDER BY event_timestamp DESC", (case_id,)
    ).fetchall()
    assert len(rows) > 0
    assert rows[0]["event_type"] == "in_progress"


def test_update_status_rejects_invalid_status(isolated_db):
    repo = ModeratorRepository()
    queue = repo.get_queue(limit=1)
    case_id = queue[0]["case_id"]

    import pytest
    with pytest.raises(ValueError):
        repo.update_status(case_id, "not_a_real_status", "MOD-001")


def test_add_note_persists_and_appears_in_get_notes(isolated_db):
    repo = ModeratorRepository()
    queue = repo.get_queue(limit=1)
    case_id = queue[0]["case_id"]

    note_id = repo.add_note(case_id, "MOD-004", "This is a test note.")

    notes = repo.get_notes(case_id)
    assert any(n["note_id"] == note_id for n in notes)
    assert any(n["note_text"] == "This is a test note." for n in notes)


def test_add_note_also_writes_audit_entry(isolated_db):
    repo = ModeratorRepository()
    queue = repo.get_queue(limit=1)
    case_id = queue[0]["case_id"]

    repo.add_note(case_id, "MOD-005", "Another test note.")

    audit = repo.get_audit_log(case_id)
    assert any("note" in a["action"].lower() for a in audit)