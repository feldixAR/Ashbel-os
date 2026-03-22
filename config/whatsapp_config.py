import os

WHATSAPP_CONFIG = {
    "phone_number_id": os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "1656261985567539"),
    "access_token": os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
    "webhook_verify_token": os.environ.get("WEBHOOK_VERIFY_TOKEN", "ashbelos_webhook_2026"),
    "api_version": "v19.0",
    "base_url": "https://graph.facebook.com/v19.0",
}
