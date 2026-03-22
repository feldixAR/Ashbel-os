"""
contacts.py — Contacts Resolution Layer (Batch 5)

Resolves contact names to phone numbers from:
    1. CRM leads DB (always available)
    2. Google Contacts API (when GOOGLE_CONTACTS_TOKEN is set)

Used by WhatsApp and Calendar services to find phone numbers by name.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional, List

log = logging.getLogger(__name__)

GOOGLE_CONTACTS_TOKEN = os.getenv("GOOGLE_CONTACTS_TOKEN", "")


@dataclass
class Contact:
    name:   str
    phone:  Optional[str]
    email:  Optional[str]  = None
    source: str            = "crm"   # crm | google_contacts | manual
    lead_id: Optional[str] = None


class ContactsService:

    def resolve(self, name: str) -> Optional[Contact]:
        """
        Find a contact by name.
        Priority: CRM leads → Google Contacts → None
        """
        # 1. Search CRM
        contact = self._search_crm(name)
        if contact:
            return contact

        # 2. Search Google Contacts
        if GOOGLE_CONTACTS_TOKEN:
            contact = self._search_google_contacts(name)
            if contact:
                return contact

        return None

    def resolve_or_manual(self, name: str, phone: str = "") -> Contact:
        """Resolve or create a manual contact if not found."""
        contact = self.resolve(name)
        if contact:
            return contact
        return Contact(name=name, phone=phone or None, source="manual")

    def _search_crm(self, name: str) -> Optional[Contact]:
        """Search leads DB for a matching name."""
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            leads = LeadRepository().list_all()
            name_lower = name.lower().strip()

            # Exact match first
            for lead in leads:
                if lead.name and lead.name.lower().strip() == name_lower:
                    return Contact(
                        name=lead.name, phone=lead.phone,
                        source="crm", lead_id=lead.id,
                    )

            # Partial match (first name)
            for lead in leads:
                if lead.name and name_lower in lead.name.lower():
                    return Contact(
                        name=lead.name, phone=lead.phone,
                        source="crm", lead_id=lead.id,
                    )
        except Exception as e:
            log.error(f"[Contacts] CRM search failed: {e}")
        return None

    def _search_google_contacts(self, name: str) -> Optional[Contact]:
        """Search Google People API."""
        import json, urllib.request, urllib.error
        try:
            url = (f"https://people.googleapis.com/v1/people:searchContacts"
                   f"?query={urllib.parse.quote(name)}"
                   f"&readMask=names,phoneNumbers"
                   f"&pageSize=5")
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {GOOGLE_CONTACTS_TOKEN}"}
            )
            with urllib.request.urlopen(req) as r:
                data    = json.loads(r.read())
                results = data.get("results", [])
                if not results:
                    return None
                person  = results[0].get("person", {})
                names   = person.get("names", [{}])
                phones  = person.get("phoneNumbers", [{}])
                found_name  = names[0].get("displayName", name) if names else name
                found_phone = phones[0].get("value", "") if phones else ""
                return Contact(name=found_name, phone=found_phone,
                               source="google_contacts")
        except Exception as e:
            log.warning(f"[Contacts] Google search failed: {e}")
        return None

    def list_crm_contacts(self, limit: int = 50) -> List[Contact]:
        """Return all CRM contacts for display."""
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            leads = LeadRepository().list_all(limit=limit)
            return [
                Contact(name=l.name, phone=l.phone, source="crm", lead_id=l.id)
                for l in leads if l.name
            ]
        except Exception as e:
            log.error(f"[Contacts] list failed: {e}")
            return []


# Missing import fix
import urllib.parse

contacts_service = ContactsService()
