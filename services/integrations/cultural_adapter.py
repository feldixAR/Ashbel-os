"""
cultural_adapter.py — Israeli aluminum market message adaptation.
Pure Python — 0 AI tokens. Called before every outreach send.

adapt_message(lead, template, attempt_number) -> str
adapt_timing(audience)                        -> dict
"""

import re
import logging
from config.business_knowledge import (
    AUDIENCE_PLAYBOOK,
    ISRAELI_CULTURAL_RULES,
    ISRAELI_TIMING,
    CHANNEL_RULES,
)
from services.policy.policy_engine import get_audience

log = logging.getLogger(__name__)


class CulturalAdapter:

    def adapt_message(self, lead, template: str, attempt_number: int = 0) -> str:
        """
        Adapt outreach template for Israeli aluminum market.
        Returns adapted message string. Never raises.
        """
        try:
            return self._adapt(lead, template, attempt_number)
        except Exception as e:
            log.warning(f"[CulturalAdapter] adapt_message failed, using original: {e}")
            return template

    def _adapt(self, lead, template: str, attempt_number: int) -> str:
        audience = get_audience(lead)
        pb       = AUDIENCE_PLAYBOOK.get(audience, AUDIENCE_PLAYBOOK["general"])
        name     = (getattr(lead, "name", None) or "").split()[0] if hasattr(lead, "name") else ""

        # 1. Opening salutation
        opening = pb["opening"].format(name=name) if name else pb["opening"].replace(" {name}", "")
        if not template.startswith(("היי", "שלום", "הי ")):
            template = f"{opening},\n\n{template}"

        # 2. Remove clichés
        for cliche in ISRAELI_CULTURAL_RULES["cliche_blacklist"]:
            template = template.replace(cliche, "")

        # 3. Truncate to max WhatsApp sentences
        max_s = ISRAELI_CULTURAL_RULES["max_whatsapp_sentences"]
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', template) if s.strip()]
        if len(sentences) > max_s + 1:
            sentences = sentences[:max_s + 1]
            template  = " ".join(sentences)

        # 4. Add urgency word if high attempt
        urgency_threshold = pb.get("urgency_threshold", 2)
        if attempt_number >= urgency_threshold:
            urgency_word = ISRAELI_CULTURAL_RULES["urgency_signals"][0]
            if urgency_word not in template:
                template = template.rstrip() + f" ({urgency_word})"

        # 5. Remove audience-specific avoid words
        for word in pb.get("avoid_words", []):
            template = template.replace(word, "")

        # 6. Collapse extra whitespace/newlines
        template = re.sub(r'\n{3,}', '\n\n', template)
        template = re.sub(r'  +', ' ', template).strip()

        return template

    def adapt_timing(self, audience: str = "general") -> dict:
        """
        Returns {allowed: bool, next_slot: str|None, reason: str}.
        Checks ISRAELI_TIMING blocked periods. Pure Python.
        """
        import datetime
        now     = datetime.datetime.now()
        weekday = now.weekday()
        t       = now.time()

        for block in ISRAELI_TIMING["blocked"]:
            if block.get("all_day") and weekday == block["day"]:
                return {"allowed": False, "reason": block["reason"], "next_slot": "ראשון 08:00"}
            if "from" in block and weekday == block["day"] and t >= block["from"]:
                return {"allowed": False, "reason": block["reason"], "next_slot": "ראשון 08:00"}

        for start_h, end_h in ISRAELI_TIMING["avoid_hours"]:
            if t.hour >= start_h or t.hour < end_h:
                return {"allowed": False, "reason": "שעות לילה", "next_slot": "07:00"}

        best = ISRAELI_TIMING["best_hours"].get(audience, [(9, 17)])
        in_best = any(s <= t.hour < e for s, e in best)
        return {
            "allowed":    True,
            "reason":     "זמן מותר" + (" — שעת שיא" if in_best else ""),
            "next_slot":  None,
        }


cultural_adapter = CulturalAdapter()
