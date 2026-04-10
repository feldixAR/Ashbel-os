"""
Tests for ChiefOfStaffAgent — local policy checks, can_handle, execute structure.
No AI calls — patched.
"""
import pytest
from unittest.mock import patch, MagicMock
from agents.departments.executive.chief_of_staff_agent import ChiefOfStaffAgent
from services.storage.models.task import TaskModel


def _task(command: str = "תכנן פעולות מכירה") -> TaskModel:
    t = TaskModel()
    t.id         = "test-cos-001"
    t.trace_id   = "trace-001"
    t.input_data = {"command": command, "params": {"goal": command}}
    return t


def test_can_handle_true():
    agent = ChiefOfStaffAgent()
    assert agent.can_handle("executive", "plan_action") is True


def test_can_handle_false():
    agent = ChiefOfStaffAgent()
    assert agent.can_handle("sales", "create_lead") is False


def test_execute_timing_blocked():
    """When policy blocks timing, returns success=False without AI call."""
    agent = ChiefOfStaffAgent()
    with patch("services.policy.policy_engine.check_timing",
               return_value={"allowed": False, "reason": "שבת", "next_slot": "ראשון"}):
        result = agent.execute(_task())
    assert result.success is False
    assert "שבת" in result.message


def test_execute_calls_ai_when_timing_ok():
    """When timing ok, agent calls _classify_goal and _build_plan."""
    agent = ChiefOfStaffAgent()
    with patch("services.policy.policy_engine.check_timing",
               return_value={"allowed": True, "reason": "מותר", "next_slot": None}), \
         patch.object(agent, "_classify_goal",
                      return_value={"type": "operational", "urgency": "normal"}), \
         patch.object(agent, "_build_plan", return_value="1. צעד א\n2. צעד ב"), \
         patch.object(agent, "_log_decision"):
        result = agent.execute(_task())
    assert result.success is True
    assert "צעד א" in result.message


def test_output_keys():
    agent = ChiefOfStaffAgent()
    with patch("services.policy.policy_engine.check_timing",
               return_value={"allowed": True, "reason": "ok", "next_slot": None}), \
         patch.object(agent, "_classify_goal",
                      return_value={"type": "strategy", "urgency": "critical"}), \
         patch.object(agent, "_build_plan", return_value="תוכנית אסטרטגית"), \
         patch.object(agent, "_log_decision"):
        result = agent.execute(_task())
    assert "goal" in result.output
    assert result.output["model_tier"] == "opus"


def test_execute_never_raises():
    """execute() must never raise regardless of internal errors."""
    agent = ChiefOfStaffAgent()
    with patch.object(agent, "_local_compute", side_effect=RuntimeError("boom")):
        result = agent.execute(_task())
    assert result.success is False
