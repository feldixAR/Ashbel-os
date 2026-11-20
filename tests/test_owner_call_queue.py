from api.routes.owner_chat_intent import call_queue_reply


def task(name, action, **changes):
    return {"subject": name, "action": action, "disposition": "actionable", **changes}


def test_call_queue_distinguishes_customer_callbacks_partner_prep_and_supplier_approval():
    context = {"actions": [
        task("שותפים", "להכין עם עמית שיחת תגמול על כל הצעה", kind="internal"),
        task("ספק", "שתי שיחות סינון מומלצות. לפני פנייה נדרש אישור עמית.", kind="supplier"),
        task("פרויקט בהמתנה", "בעקבות שיחת 17.11: מעקב אחר התקדמות השלד"),
        task("עסקה שנסגרה", "לא לחייג. שיחת מעקב רק אם תתקבל בקשה."),
    ], "lead_followups": [
        task("לקוח א", "לחייג", due_date="2026-11-12"),
        task("לקוח ב", "לחייג", disposition="needs_review"),
        task("לקוח ג", "לחייג", disposition="completed"),
    ]}
    text, n = call_queue_reply(context, limit=None)
    assert n == 4
    assert "לקוח א · למעקב טלפוני" in text
    assert "לקוח ב · לבירור לפני חיוג" in text
    assert "ספק · נדרש אישור לפני פנייה" in text
    assert "שותפים · הכנת שיחה" in text
    assert all(name not in text for name in ("עסקה שנסגרה", "פרויקט בהמתנה", "לקוח ג"))
    text, n = call_queue_reply(context, limit=1, exclude="לקוח א")
    assert n == 1 and "לקוח א" not in text


def test_call_pages_cover_verified_rows_once_without_exceeding_telegram_limit():
    rows = [task(f"שותף {i:03}", "להתקשר " + "📞" * 160) for i in range(100)]
    ctx = {"actions": rows}
    seen = 0
    texts = []
    while seen < len(rows):
        page, count = call_queue_reply(ctx, offset=seen)
        assert count > 0 and len(page.encode("utf-16-le")) // 2 <= 4096
        seen += count
        texts.append(page)
    assert seen == 100
    full = "\n".join(texts)
    assert all(full.count(row["subject"] + " ·") == 1 for row in rows)
    assert call_queue_reply(ctx, offset=seen)[1] == 0


def test_full_work_list_pages_across_waiting_and_scheduled_leads():
    from api.routes.owner_chat import _task_page

    def row(i, disposition):
        return dict(subject=f"פריט {i}", action="בירור פנימי", due_date="2026-11-20",
                    disposition=disposition, kind="internal", blocked_reasons=[])

    context = dict(health="read_ok", decisions=[], capacity_state="confirmed",
                   actions=[row(i, "actionable") for i in range(12)] + [row(12, "waiting")],
                   lead_followups=[dict(row(13, "future"), source_type="lead_followup")])
    first, seen = _task_page(context, {}, "tasks")
    assert "1–3 מתוך 14" in first
    more, seen = _task_page(context, {"task_seen": list(seen)}, "more")
    assert "4–6 מתוך 14" in more and len(seen) == 6
    full, seen = _task_page(context, {}, "all_tasks")
    assert "מתוך 14" in full and "בהמתנה" in full and "מעקב ליד · עתידי" in full
    assert len(seen) == 14


def test_contact_revision_keeps_previous_page_and_checks_live_number():
    from api.routes.owner_chat_intent import previous_contacts

    rows = [task(f"ליד {i}", "לחייג", phone=f"050123450{i}") for i in range(3)]
    ctx = {"actions": [], "lead_followups": rows}
    page, count = call_queue_reply(ctx, offset=1)
    assert count == 2
    state = {"last_answer": page}
    assert list(previous_contacts(ctx, state).values()) == rows[1:]
    rows[1]["phone"] = "0509999999"
    assert list(previous_contacts(ctx, state).values()) == rows[2:]


def test_dial_entity_after_hebrew_and_emoji(monkeypatch):
    from unittest.mock import Mock
    from services import telegram_owner

    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    api = Mock(return_value={"message_id": 3})
    monkeypatch.setattr(telegram_owner, "_api", api)
    prefix = "📞 עמית\n"
    assert telegram_owner.reply(123, 2, prefix + "0501234567") == 3
    assert api.call_args.kwargs["entities"] == [
        {"type": "phone_number", "offset": len(prefix.encode("utf-16-le")) // 2, "length": 10}
    ]
