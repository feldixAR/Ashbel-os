"""
tests/test_learning_skills.py — Unit tests for skills/learning_skills.py.

All tests use a fake MemoryStore to avoid DB dependency.
"""
import importlib
import types
import sys
import pytest


# ── Fake MemoryStore ──────────────────────────────────────────────────────────

class _FakeStore:
    def __init__(self):
        self._data: dict = {}

    def write(self, ns, key, value, updated_by="test"):
        self._data[(ns, key)] = value

    def read(self, ns, key, default=None):
        return self._data.get((ns, key), default)

    def list_namespace(self, ns):
        return {k: v for (n, k), v in self._data.items() if n == ns}

    def delete(self, ns, key):
        return self._data.pop((ns, key), None) is not None

    def get_routing_override(self, task_type):
        overrides = self.read("routing", "overrides", {})
        return overrides.get(task_type)

    def set_routing_override(self, task_type, model_key):
        overrides = self.read("routing", "overrides", {})
        overrides[task_type] = model_key
        self.write("routing", "overrides", overrides)


# Install fake memory module before importing learning_skills
_fake_store = _FakeStore()

_fake_memory_mod = types.ModuleType("memory.memory_store")
_fake_memory_mod.MemoryStore = _fake_store
sys.modules.setdefault("memory", types.ModuleType("memory"))
sys.modules["memory.memory_store"] = _fake_memory_mod


# Patch _store() in learning_skills to return the fake
import skills.learning_skills as LS
LS._store = lambda: _fake_store  # type: ignore[attr-defined]


# ── Template tests ────────────────────────────────────────────────────────────

class TestTemplateTracking:
    def setup_method(self):
        _fake_store._data.clear()

    def test_record_positive_outcome_promotes_template(self):
        res = LS.record_template_outcome("follow_up", "שלום!", "reply", segment="residential")
        assert res["recorded"] is True
        assert res["promoted"] is True  # first record always promotes

    def test_record_negative_outcome_does_not_promote(self):
        # First: write a current best
        _fake_store.write("messaging", "best_follow_up_residential", "existing_best")
        # Record ignored outcome
        res = LS.record_template_outcome("follow_up", "template_b", "ignored", segment="residential")
        assert res["promoted"] is False
        # Best should remain unchanged
        best = LS.get_best_template("follow_up", segment="residential")
        assert best == "existing_best"

    def test_get_best_template_fallback_chain(self):
        _fake_store.write("messaging", "best_follow_up", "generic_best")
        result = LS.get_best_template("follow_up", segment="commercial", channel="whatsapp")
        assert result == "generic_best"

    def test_get_best_template_segment_channel_preferred(self):
        _fake_store.write("messaging", "best_follow_up", "generic")
        _fake_store.write("messaging", "best_follow_up_commercial_whatsapp", "specific")
        result = LS.get_best_template("follow_up", segment="commercial", channel="whatsapp")
        assert result == "specific"

    def test_stats_accumulate(self):
        LS.record_template_outcome("intro", "t1", "reply")
        LS.record_template_outcome("intro", "t1", "ignored")
        LS.record_template_outcome("intro", "t1", "meeting")
        key = ("messaging", "stats_intro")
        stats = _fake_store._data[key]
        assert stats["total"] == 3
        assert stats["reply"] == 1
        assert stats["meeting"] == 1
        assert stats["ignored"] == 1


# ── Source strategy tests ─────────────────────────────────────────────────────

class TestSourceStrategy:
    def setup_method(self):
        _fake_store._data.clear()

    def test_record_source_outcome(self):
        res = LS.record_source_outcome("google_maps", "residential", leads_found=10, leads_qualified=4)
        assert res["recorded"] is True

    def test_best_source_requires_3_runs(self):
        LS.record_source_outcome("google_maps", "residential", 10, 4)
        LS.record_source_outcome("google_maps", "residential", 10, 4)
        # Only 2 runs — no best yet
        assert LS.get_best_source("residential") is None

    def test_best_source_selected_after_3_runs(self):
        for _ in range(3):
            LS.record_source_outcome("google_maps", "residential", 10, 7)
        best = LS.get_best_source("residential")
        assert best == "google_maps"

    def test_best_source_selects_higher_rate(self):
        for _ in range(3):
            LS.record_source_outcome("google_maps", "commercial", 10, 2)  # 20%
        for _ in range(3):
            LS.record_source_outcome("manual", "commercial", 10, 6)       # 60%
        best = LS.get_best_source("commercial")
        assert best == "manual"

    def test_get_source_stats_empty(self):
        assert LS.get_source_stats("unknown_goal") == {}


# ── Agent performance tests ───────────────────────────────────────────────────

class TestAgentPerformance:
    def setup_method(self):
        _fake_store._data.clear()

    def test_record_success(self):
        stats = LS.record_agent_outcome("lead_acquisition_agent", "discover", success=True, latency_ms=250)
        assert stats["success"] == 1
        assert stats["total"] == 1
        assert stats["avg_latency_ms"] == 250

    def test_record_failure(self):
        stats = LS.record_agent_outcome("lead_acquisition_agent", "discover", success=False)
        assert stats["failure"] == 1
        assert stats["success"] == 0

    def test_accumulates_multiple_outcomes(self):
        LS.record_agent_outcome("agent_x", "score", success=True, latency_ms=100)
        LS.record_agent_outcome("agent_x", "score", success=True, latency_ms=200)
        stats = LS.record_agent_outcome("agent_x", "score", success=False, latency_ms=300)
        assert stats["total"] == 3
        assert stats["success"] == 2
        assert stats["failure"] == 1

    def test_global_summary_updated(self):
        LS.record_agent_outcome("agent_z", "act", success=True)
        summary = _fake_store.read("global", "agent_summary", {})
        assert "agent_z" in summary
        assert summary["agent_z"]["success_rate"] == 1.0

    def test_get_agent_stats_empty(self):
        assert LS.get_agent_stats("ghost_agent", "missing") == {}


# ── Conversion tracking tests ─────────────────────────────────────────────────

class TestConversionTracking:
    def setup_method(self):
        _fake_store._data.clear()

    def test_record_converted_lead(self):
        res = LS.record_lead_conversion("lead_001", "residential", "google_maps",
                                        score_at_outreach=82, converted=True)
        assert res["bucket"] == "hot"
        assert res["stats"]["converted"] == 1

    def test_score_buckets(self):
        assert LS._score_bucket(85) == "hot"
        assert LS._score_bucket(65) == "high"
        assert LS._score_bucket(45) == "medium"
        assert LS._score_bucket(20) == "low"

    def test_conversion_stats_structure(self):
        LS.record_lead_conversion("l1", "seg", "src", 75, True)
        LS.record_lead_conversion("l2", "seg", "src", 75, False)
        stats = LS.get_conversion_stats()
        assert "hot" in stats
        assert "high" in stats
        assert stats["high"]["total"] == 2
        assert stats["high"]["rate"] == 0.5


# ── Model routing tests ───────────────────────────────────────────────────────

class TestRoutingRecommendations:
    def setup_method(self):
        _fake_store._data.clear()

    def test_recommend_returns_default_when_no_override(self):
        assert LS.recommend_model("batch_score", default="haiku") == "haiku"

    def test_promote_model_and_recall(self):
        LS.promote_model("batch_score", "sonnet", reason="better accuracy")
        result = LS.recommend_model("batch_score", default="haiku")
        assert result == "sonnet"

    def test_promote_stores_reason(self):
        LS.promote_model("inbound_draft", "opus", reason="higher reply rate")
        reason = _fake_store.read("routing", "reason_inbound_draft")
        assert reason == "higher reply rate"
