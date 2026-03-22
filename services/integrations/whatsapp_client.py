import requests
import logging

logger = logging.getLogger(__name__)
WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"

class WhatsAppClient:
    def __init__(self, phone_number_id: str, access_token: str):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.base_url = f"{WHATSAPP_API_URL}/{phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def send_text(self, to: str, message: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": message}
        }
        try:
            r = requests.post(self.base_url, headers=self.headers, json=payload, timeout=10)
            r.raise_for_status()
            logger.info(f"WhatsApp sent to {to}: {r.status_code}")
            return {"success": True, "message_id": r.json().get("messages", [{}])[0].get("id"), "to": to}
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return {"success": False, "error": str(e)}

    def send_template(self, to: str, template_name: str, language: str = "he", components: list = None) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components or []
            }
        }
        try:
            r = requests.post(self.base_url, headers=self.headers, json=payload, timeout=10)
            r.raise_for_status()
            return {"success": True, "message_id": r.json().get("messages", [{}])[0].get("id")}
        except Exception as e:
            logger.error(f"WhatsApp template failed: {e}")
            return {"success": False, "error": str(e)}

    def mark_as_read(self, message_id: str) -> bool:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        try:
            r = requests.post(self.base_url, headers=self.headers, json=payload, timeout=10)
            return r.status_code == 200
        except:
            return False
