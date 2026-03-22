class IntentParser:
    def parse(self, text: str):
        text_lower = text.lower()

        # SALES
        if any(word in text_lower for word in ["lead", "ליד", "לקוח", "מכירה"]):
            return {
                "intent": "sales",
                "task": "handle_lead",
                "entities": {}
            }

        # WHATSAPP (future use)
        if any(word in text_lower for word in ["וואטסאפ", "whatsapp", "שלח הודעה"]):
            return {
                "intent": "communication",
                "task": "send_message",
                "entities": {}
            }

        # CALENDAR (future use)
        if any(word in text_lower for word in ["פגישה", "meeting", "schedule"]):
            return {
                "intent": "calendar",
                "task": "schedule_event",
                "entities": {}
            }

        # DEFAULT FALLBACK
        return {
            "intent": "unknown",
            "task": "unknown",
            "entities": {}
        }
