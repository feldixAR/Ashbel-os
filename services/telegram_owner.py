"""Transport and webhook registration for the existing owner's private chat."""

import hashlib
import hmac
import logging
import os
import re
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)
WEBHOOK_PATH = "/api/telegram/owner-webhook"
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def owner_chat_id():
    value = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return int(value) if re.fullmatch(r"[1-9][0-9]{0,15}", value) else None


def webhook_secret():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return ""
    return hmac.new(token.encode(), b"ashbelos/telegram-owner-webhook/v1", hashlib.sha256).hexdigest()


def _api(method, **payload):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    try:
        response = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=8, allow_redirects=False)
        data = response.json()
        if response.ok and isinstance(data, dict) and data.get("ok") is True:
            return data.get("result")
        log.warning("Telegram owner API method=%s rejected status=%s", method, response.status_code)
    except (requests.RequestException, ValueError):
        log.warning("Telegram owner API method=%s unavailable", method)
    return None


def reply(chat_id, message_id, text):
    """Reply in the verified private chat without enabling scheduled sends."""
    if chat_id != owner_chat_id() or chat_id is None or not webhook_secret():
        return None
    # Telegram entity offsets and message budgets count UTF-16 code units.
    text = text.encode("utf-16-le")[:8192].decode("utf-16-le", errors="ignore")
    entities = [{"type": "phone_number",
                 "offset": len(text[:match.start()].encode("utf-16-le")) // 2,
                 "length": len(match.group())}
                for match in re.finditer(r"(?m)^(?:0|\+972[- ]?)\d{1,2}[- ]?\d{7}$", text)]
    result = _api("sendMessage", chat_id=chat_id, text=text, entities=entities,
                  reply_parameters={"message_id": message_id, "allow_sending_without_reply": True})
    return result.get("message_id") if isinstance(result, dict) else None


def register_webhook(domain):
    secret, owner = webhook_secret(), owner_chat_id()
    if not secret or owner is None or not re.fullmatch(r"[a-zA-Z0-9.-]+", domain):
        raise ValueError("missing or invalid bot, private chat or domain configuration")
    bot = _api("getMe")
    if not bot or not bot.get("username"):
        raise ValueError("bot identity could not be verified")
    log.info("Telegram owner bot @%s", bot["username"])
    chat = _api("getChat", chat_id=owner)
    if not chat or chat.get("type") != "private" or chat.get("id") != owner:
        raise ValueError("configured owner chat is not accessible as a private chat")
    existing = _api("getWebhookInfo")
    if not isinstance(existing, dict):
        raise ValueError("existing webhook could not be verified")
    current = urlsplit(existing.get("url", ""))
    if current.netloc and (current.hostname != domain.lower() or current.path not in {
        WEBHOOK_PATH, "/api/telegram/webhook"
    }):
        raise ValueError("bot has a webhook outside this AshbelOS route")
    url = f"https://{domain}{WEBHOOK_PATH}"
    if _api("setWebhook", url=url, secret_token=secret, allowed_updates=["message"],
            max_connections=1) is not True:
        raise ValueError("Telegram did not accept the webhook")
    registered = _api("getWebhookInfo")
    if not registered or registered.get("url") != url or registered.get("max_connections") != 1:
        raise ValueError("webhook registration could not be read back")
    log.info("Telegram owner webhook verified @%s", bot["username"])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("domain")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        register_webhook(args.domain)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
