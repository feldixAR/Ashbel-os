"""A text API response cannot stand in for business execution evidence."""
from unittest.mock import patch

from engines import claude_dispatch as bridge
from services.storage.db import create_all_tables
from services.storage.repositories.claude_task_repo import ClaudeTaskRepository


def test_legacy_completed_task_is_explicitly_not_verified():
    create_all_tables()
    task = ClaudeTaskRepository().create(instruction="synthetic old result", status="completed",
                                        approved=True, summary="No data access")
    view = task.to_gpt_view()
    assert view["status"] == "completed"
    assert view["business_outcome"] == "not_verified"
    assert view["execution_verified"] is False


def test_claimed_file_changes_are_discarded_without_tool_evidence():
    result = bridge._parse_response('{"summary":"claimed change","changed_files":["app.py"],"diff_available":true,"outcome":"completed"}')
    assert result["changed_files"] == []
    assert result["diff_available"] is False
    assert result["business_outcome"] == "not_verified"
    assert result["tool_execution_available"] is False


def test_blocked_result_keeps_transport_status_separate_and_never_notifies():
    create_all_tables()
    result = bridge._parse_response('{"summary":"source is missing","changed_files":[],"outcome":"blocked","missing":["CRM access"]}')
    with patch.object(bridge, "_call_claude_api", return_value=result), patch.object(bridge, "_notify_telegram") as notify:
        response = bridge.dispatch({"instruction": "synthetic data query", "approved": True})
        notify.assert_not_called()
    assert response["status"] == "completed"  # provider call lifecycle only
    assert response["business_outcome"] == "blocked"
    assert response["missing"] == ["CRM access"]
    assert response["execution_verified"] is False
    stored = ClaudeTaskRepository().get(response["task_id"]).to_gpt_view()
    assert stored["business_outcome"] == "blocked" and stored["execution_verified"] is False
