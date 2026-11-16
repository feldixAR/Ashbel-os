from api.routes.intake import _business_score, _missing_fields


def test_explicit_aluminum_mid_skeleton_is_hot_now():
    rec = {
        "name": "Synthetic Owner",
        "phone": "0501234567",
        "email": "owner@example.com",
        "city": "Ariel",
        "notes": "מבקש אלומיניום לבית, אמצע שלד",
        "work_type": "אלומיניום",
        "project_stage": "אמצע שלד",
        "address": "Ariel",
    }
    readiness = {"ready_for_proposal": False}

    result = _business_score(rec, readiness)

    assert result["aluminum_intent"] == "explicit_aluminum"
    assert result["construction_stage"] == "mid_skeleton"
    assert result["score_label"] == "hot_now"
    assert result["timing_window"] == "השבוע"
    assert "אלומיניום" in result["business_reason"]
    assert result["score_breakdown"]["intent"] == 35


def test_all_fields_plaster_requires_aluminum_clarification():
    rec = {
        "name": "Synthetic Owner",
        "phone": "0501234567",
        "city": "Oranit",
        "notes": "מבקשים הצעות מכל התחומים, שלב טיח",
        "project_stage": "טיח",
    }
    readiness = {}

    result = _business_score(rec, readiness)

    assert result["aluminum_intent"] == "all_fields"
    assert result["construction_stage"] == "plaster"
    assert result["score_label"] == "clarify"
    assert "האם האלומיניום כבר נסגר" in result["recommended_action"]


def test_planning_with_explicit_aluminum_is_future_follow_up():
    rec = {
        "name": "Synthetic Owner",
        "email": "owner@example.com",
        "city": "Nofei Nehemia",
        "notes": "מתעניין באלומיניום בשלב תכנון",
        "project_stage": "תכנון",
    }
    readiness = {}

    result = _business_score(rec, readiness)

    assert result["aluminum_intent"] == "explicit_aluminum"
    assert result["construction_stage"] == "planning"
    assert result["score_label"] in ("warm", "follow_up")
    assert result["timing_window"] == "כמה חודשים"


def test_missing_fields_names_action_blockers():
    rec = {"name": "Synthetic Owner", "notes": "אלומיניום"}
    readiness = {
        "missing_plans": True,
        "missing_measurements": True,
        "missing_photos": True,
        "missing_project_stage": True,
    }

    missing = _missing_fields(rec, readiness)

    assert "טלפון או מייל" in missing
    assert "תכניות" in missing
    assert "מידות" in missing
    assert "תמונות" in missing
    assert "שלב פרויקט" in missing


def test_explicit_english_aluminum_words_are_case_insensitive():
    from api.routes.intake import _classify_aluminum_intent
    for text in ('aluminum belgian window', 'ALUMINIUM windows', 'AlUmInUm',
                 'Request: (aluminium) windows.'):
        intent, _, points, confidence = _classify_aluminum_intent(text)
        assert intent == 'explicit_aluminum', text
        assert points == 35
        assert confidence == 'high'


def test_belgian_window_without_material_does_not_imply_aluminum():
    from api.routes.intake import _classify_aluminum_intent
    for text in ('belgian window', 'steel belgian window', 'Steel Belgian Window',
                 'prealuminum', 'aluminiumworks', 'aluminumized'):
        assert _classify_aluminum_intent(text)[0] != 'explicit_aluminum', text
        result = _business_score({'work_type': text}, {'ready_for_proposal': True})
        assert result['aluminum_intent'] != 'explicit_aluminum'
        assert result['score_label'] == 'skip'


def test_explicit_english_material_preserves_business_score_thresholds():
    record = {'name': 'Synthetic Owner', 'phone': '0501234567',
              'email': 'owner@example.com', 'city': 'Ariel',
              'work_type': 'Aluminium belgian window', 'project_stage': 'ready'}
    result = _business_score(record, {'ready_for_proposal': True})
    assert result['aluminum_intent'] == 'explicit_aluminum'
    assert result['construction_stage'] == 'unknown'
    assert result['score_breakdown']['intent'] == 35
    assert result['score_total'] == 60
    assert result['score_label'] == 'warm'
