from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_index_loads_business_import_assets():
    html = read("ui/index.html")

    assert "/ui/css/import_review.css?v=bir1" in html
    assert "/ui/js/components/upload_modal.js?v=bir1" in html
    assert "dir=\"rtl\"" in html
    assert "id=\"uploadModal\"" in html


def test_upload_modal_uses_safe_business_language():
    js = read("ui/js/components/upload_modal.js")

    assert "אשר לידים מומלצים בלבד" in js
    assert "העבר לאישור ייבוא" in js
    assert "סמן לייבוא" in js
    assert "דורש בדיקה" in js
    assert "עדיין לא נכתבו לידים למערכת ולא נשלחה שום הודעה ללקוחות" in js
    assert "_resetFileInput" in js


def test_upload_modal_renders_business_scoring_context():
    js = read("ui/js/components/upload_modal.js")

    assert "aluminum_intent_label" in js
    assert "construction_stage_label" in js
    assert "timing_window" in js
    assert "business_reason" in js
    assert "recommended_action" in js
    assert "score_breakdown" in js
    assert "missing_fields" in js
    assert "חסר להצעה" in js
    assert "ניקוד: כוונה" in js


def test_business_import_css_supports_mobile_review_cards():
    css = read("ui/css/import_review.css")

    assert ".um-business-badges" in css
    assert ".um-row-missing" in css
    assert ".um-score-breakdown" in css
    assert "@media (max-width: 640px)" in css
    assert "min-height: 40px" in css
