"""
Tests for CulturalAdapter — pure Python, 0 AI tokens.
"""
import pytest
from services.integrations.cultural_adapter import CulturalAdapter


def _lead(name="יוסי", notes="", status="", source=""):
    return type("L", (), {"name": name, "notes": notes,
                           "status": status, "source": source})()


def test_adapt_message_returns_string():
    ca = CulturalAdapter()
    result = ca.adapt_message(_lead(), "שלום, אנחנו אשבל אלומיניום.")
    assert isinstance(result, str)
    assert len(result) > 0


def test_removes_cliche():
    ca = CulturalAdapter()
    msg = "הזדמנות פז לחלונות חדשים!"
    result = ca.adapt_message(_lead(), msg)
    assert "הזדמנות פז" not in result


def test_adds_opening_salutation():
    ca = CulturalAdapter()
    msg = "אנחנו מציעים חלונות אלומיניום."
    result = ca.adapt_message(_lead(name="דוד"), msg)
    assert "דוד" in result


def test_truncates_long_message():
    ca = CulturalAdapter()
    # 6 sentences — should be truncated to max_whatsapp_sentences + 1
    msg = "א. ב. ג. ד. ה. ו."
    result = ca.adapt_message(_lead(), msg)
    sentences = [s.strip() for s in result.split(".") if s.strip()]
    assert len(sentences) <= 5


def test_urgency_added_at_threshold():
    ca = CulturalAdapter()
    msg = "שלום, אנחנו אשבל אלומיניום."
    result = ca.adapt_message(_lead(), msg, attempt_number=3)
    assert "עכשיו" in result


def test_no_urgency_below_threshold():
    ca = CulturalAdapter()
    msg = "שלום, אנחנו אשבל אלומיניום."
    result = ca.adapt_message(_lead(), msg, attempt_number=0)
    assert "עכשיו" not in result


def test_adapt_timing_returns_dict():
    ca = CulturalAdapter()
    result = ca.adapt_timing("contractors")
    assert "allowed" in result
    assert "reason" in result


def test_never_raises_on_bad_lead():
    ca = CulturalAdapter()
    bad_lead = None
    result = ca.adapt_message(bad_lead, "הודעה.", attempt_number=0)
    assert isinstance(result, str)
