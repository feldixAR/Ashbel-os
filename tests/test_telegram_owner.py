from unittest.mock import Mock

import pytest
from flask import Flask

from api.middleware import ok
from api.routes import commands, telegram
from memory.memory_store import MemoryStore
from services import telegram_owner


@pytest.fixture
def webhook(monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-only")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    app = Flask(__name__)
    app.register_blueprint(telegram.bp, url_prefix="/api")
    client = app.test_client()
    state = {}

    def read(namespace, key, default):
        return state.copy()

    def write(namespace, key, value, updated_by):
        state.update(value)
        for field in state.keys() - value.keys():
            del state[field]

    monkeypatch.setattr(MemoryStore, "read", read)
    monkeypatch.setattr(MemoryStore, "write", write)
    monkeypatch.setattr(telegram_owner, "reply", Mock(return_value=100))
    headers = {telegram_owner.SECRET_HEADER: telegram_owner.webhook_secret()}
    return client, headers, state


def message(text="מה המשימות שלי להיום?", message_id=1):
    return {"message": {"chat": {"id": 123, "type": "private"},
                        "from": {"id": 123, "is_bot": False},
                        "text": text, "message_id": message_id}}


def test_owner_review_and_replay(webhook, monkeypatch):
    client, headers, state = webhook
    engine = Mock(side_effect=lambda *args, **kwargs: ok({
        "message": "עדכון מאומת", "event_id": "event", "intent": "business_review",
        "context_event_id": "review",
    }))
    monkeypatch.setattr(commands, "_business_update", engine)
    assert client.post(telegram_owner.WEBHOOK_PATH, json=message(), headers=headers).status_code == 200
    assert client.post(telegram_owner.WEBHOOK_PATH, json=message(), headers=headers).json["data"]["status"] == "duplicate"
    assert client.post(telegram_owner.WEBHOOK_PATH, json=message("ומה עכשיו?", 2), headers=headers).status_code == 200
    assert engine.call_args.args == ("ומה עכשיו?", "review", None)
    assert engine.call_args.kwargs["source_ref"] == "ashbelos:owner-telegram"
    assert state["last_message_id"] == 2
    assert telegram_owner.reply.call_count == 2


def test_unauthorized_updates_do_not_reach_engine(webhook, monkeypatch):
    client, headers, _ = webhook
    engine = Mock()
    monkeypatch.setattr(commands, "_business_update", engine)
    assert client.post(telegram_owner.WEBHOOK_PATH, json=message()).status_code == 401
    assert client.post("/api/telegram/webhook", json=message(), headers=headers).status_code == 404
    data = message()
    data["message"]["chat"]["type"] = "group"
    assert client.post(telegram_owner.WEBHOOK_PATH, json=data, headers=headers).json["data"]["status"] == "ignored"
    data = message()
    data["message"]["from"]["id"] = 456
    assert client.post(telegram_owner.WEBHOOK_PATH, json=data, headers=headers).json["data"]["status"] == "ignored"
    engine.assert_not_called()
    telegram_owner.reply.assert_not_called()


def test_provider_failure_can_retry_same_delivery_id(webhook, monkeypatch):
    client, headers, state = webhook
    engine = Mock(side_effect=lambda *args, **kwargs: ok({
        "message": "נרשם", "event_id": "event", "intent": "business_update", "crm_cell": "F16",
    }))
    monkeypatch.setattr(commands, "_business_update", engine)
    telegram_owner.reply.side_effect = [None, 100]
    data = message("עדכון פנימי")
    assert client.post(telegram_owner.WEBHOOK_PATH, json=data, headers=headers).status_code == 503
    assert not state
    assert client.post(telegram_owner.WEBHOOK_PATH, json=data, headers=headers).status_code == 200
    assert engine.call_args_list[0].kwargs["delivery_id"] == engine.call_args_list[1].kwargs["delivery_id"]


def test_registration_preserves_other_webhook(webhook, monkeypatch):
    api = Mock(side_effect=[{"username": "testbot"}, {"id": 123, "type": "private"},
                           {"url": "https://other.example/telegram"}])
    monkeypatch.setattr(telegram_owner, "_api", api)
    with pytest.raises(ValueError, match="outside"):
        telegram_owner.register_webhook("app.example")
    assert [call.args[0] for call in api.call_args_list] == ["getMe", "getChat", "getWebhookInfo"]


@pytest.mark.parametrize("text", [
    "מה המשימות שלי היום",
    "מה המשימות שלי להיום?",
    "מה יש לי לעשות היום?",
    "מה כדאי לעשות היום?",
])
def test_daily_work_review_ignores_pending_project_clarification(webhook, monkeypatch, text):
    from services.business_events import runtime
    from services.integrations import business_source

    client, headers, state = webhook
    state["pending_message"] = "מה המשימות שלי היום"
    monkeypatch.setenv("ASHBEL_CRM_WRITEBACK_SOURCE", "owner_internal")
    monkeypatch.setenv("ASHBEL_CRM_WRITEBACK_ENABLED", "false")
    monkeypatch.setattr(runtime, "enabled", lambda: True)
    context = {"health": "read_ok", "snapshot_sha256": "snapshot", "actions": []}
    monkeypatch.setattr(business_source, "load_business_context", lambda: context)

    review = Mock(side_effect=lambda *args: ok({
        "message": "המשימה הראשונה מתור העבודה",
        "event_id": "review-event",
        "intent": "business_review",
    }))
    monkeypatch.setattr(commands, "_business_review", review)

    response = client.post(telegram_owner.WEBHOOK_PATH, json=message(text), headers=headers)
    assert response.status_code == 200
    review.assert_called_once_with(runtime, "owner_internal", context, None, "portfolio", "ashbelos:owner-telegram")
    telegram_owner.reply.assert_called_once_with(123, 1, "המשימה הראשונה מתור העבודה")
    assert "pending_message" not in state
