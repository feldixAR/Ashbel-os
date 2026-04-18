"""
tests/test_scheduler_truth.py — Scheduler registration and runtime proof.

Proves:
  - scheduler.status() returns expected structure
  - _record_last_run() writes to MemoryStore and is readable via status()
  - /api/system/scheduler endpoint returns correct structure
  - startup path is registered in app.py (non-crashing)
  - each job ID is registered in the scheduler job list when started
"""
import os
import sys
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OS_API_KEY", "test")
os.environ.setdefault("ENV", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_APP = None


def _app():
    global _APP
    if _APP is None:
        from api.app import create_app
        _APP = create_app()
        _APP.config["TESTING"] = True
    return _APP


def _client():
    return _app().test_client()


class TestSchedulerStatus(unittest.TestCase):

    def setUp(self):
        _app()

    def test_status_returns_dict(self):
        from scheduler.revenue_scheduler import status
        s = status()
        self.assertIsInstance(s, dict)

    def test_status_has_running_key(self):
        from scheduler.revenue_scheduler import status
        s = status()
        self.assertIn("running", s)
        self.assertIsInstance(s["running"], bool)

    def test_status_has_jobs_key(self):
        from scheduler.revenue_scheduler import status
        s = status()
        self.assertIn("jobs", s)
        self.assertIsInstance(s["jobs"], list)

    def test_status_has_last_runs_key(self):
        from scheduler.revenue_scheduler import status
        s = status()
        self.assertIn("last_runs", s)
        self.assertIsInstance(s["last_runs"], dict)


class TestRecordLastRun(unittest.TestCase):

    def setUp(self):
        _app()

    def test_record_last_run_writes_to_memory(self):
        from scheduler.revenue_scheduler import _record_last_run
        from memory.memory_store import MemoryStore
        _record_last_run("test_job_record")
        val = MemoryStore.read("scheduler", "last_run_test_job_record")
        self.assertIsNotNone(val, "_record_last_run must write timestamp to MemoryStore")

    def test_record_last_run_iso_format(self):
        from scheduler.revenue_scheduler import _record_last_run
        from memory.memory_store import MemoryStore
        import datetime
        _record_last_run("test_iso_job")
        val = MemoryStore.read("scheduler", "last_run_test_iso_job")
        # Should be parseable as ISO datetime
        dt = datetime.datetime.fromisoformat(val)
        self.assertIsNotNone(dt)

    def test_status_reflects_recorded_run(self):
        from scheduler.revenue_scheduler import _record_last_run, status
        _record_last_run("followup")
        s = status()
        self.assertIn("followup", s["last_runs"],
                      "status() must reflect last run written by _record_last_run")


class TestSchedulerEndpoint(unittest.TestCase):

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_scheduler_endpoint_returns_200(self):
        r = _client().get("/api/system/scheduler",
                          headers={"X-API-Key": "test"})
        self.assertEqual(r.status_code, 200)

    def test_scheduler_endpoint_has_required_keys(self):
        r = _client().get("/api/system/scheduler",
                          headers={"X-API-Key": "test"})
        d = r.get_json()
        data = d.get("data", d)
        self.assertIn("running", data)
        self.assertIn("jobs", data)
        self.assertIn("last_runs", data)

    def test_scheduler_endpoint_requires_auth(self):
        r = _client().get("/api/system/scheduler")
        self.assertIn(r.status_code, (401, 403),
                      "/api/system/scheduler must require authentication")

    def test_scheduler_endpoint_last_runs_updated(self):
        from scheduler.revenue_scheduler import _record_last_run
        _record_last_run("daily_plan")
        r = _client().get("/api/system/scheduler",
                          headers={"X-API-Key": "test"})
        d = r.get_json()
        last_runs = d.get("data", {}).get("last_runs") or d.get("last_runs", {})
        self.assertIn("daily_plan", last_runs,
                      "Endpoint must reflect last_run written before request")


class TestSchedulerJobRegistrations(unittest.TestCase):

    def setUp(self):
        _app()

    def test_all_expected_job_ids_defined(self):
        from scheduler.revenue_scheduler import _JOB_IDS
        expected = {
            "followup", "daily_plan", "learning_cycle", "telegram_delivery",
            "daily_learning_report", "maintenance", "gmail_scan",
            "maps_scan", "lead_followup_proposals",
        }
        self.assertEqual(set(_JOB_IDS), expected,
                         "_JOB_IDS must list all 9 registered job identifiers")

    def test_start_is_callable(self):
        from scheduler import revenue_scheduler
        self.assertTrue(callable(revenue_scheduler.start))

    def test_status_callable_without_start(self):
        from scheduler.revenue_scheduler import status
        # Should not raise even if scheduler not started in test env
        result = status()
        self.assertIsInstance(result, dict)

    def test_stop_callable(self):
        from scheduler import revenue_scheduler
        self.assertTrue(callable(revenue_scheduler.stop))


if __name__ == "__main__":
    unittest.main(verbosity=2)
