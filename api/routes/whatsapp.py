from flask import Blueprint, request, jsonify
import logging, os
from services.integrations.whatsapp_client import WhatsAppClient
from orchestration.orchestrator import Orchestrator

logger = logging.getLogger(__name__)
whatsapp_bp = Blueprint("whatsapp", __name__)

PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "1656261985567539")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "ashbelos_webhook_2026")

def get_client():
    return WhatsAppClient(PHONE_NUMBER_ID, WHATSAPP_TOKEN)

@whatsapp_bp.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return challenge, 200
    return "Forbidden", 403

@whatsapp_bp.route("/webhook", methods=["POST"])
def receive_webhook():
    data = request.get_json()
    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        for msg in messages:
            from_number = msg.get("from")
            msg_id = msg.get("id")
            msg_type = msg.get("type")
            client = get_client()
            client.mark_as_read(msg_id)
            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
                logger.info(f"Incoming WhatsApp from {from_number}: {text}")
                orch = Orchestrator()
                result = orch.handle(text)
                reply = result.get("response") or result.get("message") or "✅ התקבל"
                client.send_text(from_number, reply)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return jsonify({"status": "ok"}), 200

@whatsapp_bp.route("/send", methods=["POST"])
def send_message():
    data = request.get_json()
    to = data.get("to")
    message = data.get("message")
    if not to or not message:
        return jsonify({"error": "to and message required"}), 400
    client = get_client()
    result = client.send_text(to, message)
    return jsonify(result)

@whatsapp_bp.route("/status", methods=["GET"])
def whatsapp_status():
    return jsonify({
        "phone_number_id": PHONE_NUMBER_ID,
        "token_configured": bool(WHATSAPP_TOKEN),
        "webhook_verify_token": WEBHOOK_VERIFY_TOKEN,
        "status": "active" if WHATSAPP_TOKEN else "missing_token"
    })
