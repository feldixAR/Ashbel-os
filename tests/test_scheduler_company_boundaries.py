"""Scheduled legacy import/outreach requires opt-in and cannot bypass company sources."""
from unittest.mock import patch

import pytest

FLAGS = ("ASHBEL_BUSINESS_EVENTS_ENABLED", "ASHBEL_SOURCE_CONTEXT_ENABLED",
         "ASHBEL_SOURCE_SYNC_ENABLED", "ASHBEL_SOURCE_DISCOVERY_ENABLED", "ASHBEL_PRICING_SOURCE_ENABLED")


def clear(monkeypatch):
    for flag in FLAGS + ("ASHBEL_LEGACY_SCHEDULED_INTAKE_ENABLED", "ASHBEL_LEGACY_SCHEDULED_OUTREACH_ENABLED"):
        monkeypatch.delenv(flag, raising=False)


def test_credentials_or_disabled_company_flags_never_authorize_scheduled_side_effects(monkeypatch):
    clear(monkeypatch)
    monkeypatch.setenv("GMAIL_CREDENTIALS_JSON", "synthetic-configured")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "synthetic-configured")
    from scheduler.revenue_scheduler import _job_followup, _job_gmail_scan, _job_maps_scan
    with patch("engines.outreach_engine.outreach_engine.run_followup_batch", side_effect=AssertionError("unapproved send")), \
         patch("services.integrations.gmail_listener.scan_inbox", side_effect=AssertionError("duplicate CRM")), \
         patch("services.integrations.lead_scraper.scrape", side_effect=AssertionError("duplicate CRM")):
        assert _job_followup()["status"] == "blocked"
        assert _job_gmail_scan()["status"] == "blocked"
        assert _job_maps_scan()["status"] == "blocked"


@pytest.mark.parametrize("flag", FLAGS)
def test_any_company_component_blocks_legacy_even_with_legacy_opt_in(monkeypatch, flag):
    clear(monkeypatch)
    monkeypatch.setenv(flag, "true")
    monkeypatch.setenv("ASHBEL_LEGACY_SCHEDULED_INTAKE_ENABLED", "true")
    monkeypatch.setenv("ASHBEL_LEGACY_SCHEDULED_OUTREACH_ENABLED", "true")
    from scheduler.revenue_scheduler import _job_followup, _job_gmail_scan, _job_maps_scan, _job_lead_followup_proposals
    with patch("services.business_events.runtime.poll_source_and_process", return_value={"status":"governed"}), \
         patch("services.integrations.source_discovery.scan_sources", return_value={"status":"governed"}), \
         patch("engines.outreach_engine.outreach_engine.run_followup_batch", side_effect=AssertionError("unapproved send")), \
         patch("services.integrations.gmail_listener.scan_inbox", side_effect=AssertionError("duplicate CRM")), \
         patch("services.integrations.lead_scraper.scrape", side_effect=AssertionError("duplicate CRM")):
        assert _job_followup()["status"] in {"blocked", "governed"}
        assert _job_gmail_scan()["status"] == "blocked"
        assert _job_maps_scan()["status"] in {"blocked", "governed"}
        assert _job_lead_followup_proposals()["status"] == "blocked"


def test_deliberate_legacy_intake_opt_in_remains_available_outside_company_mode(monkeypatch):
    clear(monkeypatch)
    monkeypatch.setenv("ASHBEL_LEGACY_SCHEDULED_INTAKE_ENABLED", "true")
    from scheduler.revenue_scheduler import _job_gmail_scan
    with patch("services.integrations.gmail_listener.scan_inbox", return_value={"created":0}) as scan:
        _job_gmail_scan()
        scan.assert_called_once_with(max_results=20)
