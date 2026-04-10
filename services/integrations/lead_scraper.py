"""
lead_scraper.py — Google Maps category scraper for aluminum leads.

Input:  city (str) + category (str)
Output: List[{name, phone, address, category, source="maps"}]

Max 50 leads/run, rate limit 1 req/sec, dedup by phone vs existing leads.
Falls back to stub when GOOGLE_MAPS_API_KEY not set.
"""

import logging
import os
import re
import time
import datetime

log = logging.getLogger(__name__)

CATEGORIES = ["קבלנים", "אדריכלים", "מעצבי פנים", "יזמי נדלן"]
_PHONE_RE  = re.compile(r'0[5-9]\d[-\s]?\d{3}[-\s]?\d{4}')
_MAX_LEADS = 50
_RATE_SEC  = 1.0


def _existing_phones() -> set:
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        leads = LeadRepository().list_all()
        return {re.sub(r'[-\s]', '', getattr(l, 'phone', '') or '') for l in leads if getattr(l, 'phone', '')}
    except Exception:
        return set()


def scrape(city: str, category: str) -> dict:
    """
    Scrape Google Maps Places API for leads in city+category.
    Returns {leads: list, total: int, mode: str}.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        log.info("[LeadScraper] GOOGLE_MAPS_API_KEY not set — stub mode")
        return {"leads": [], "total": 0, "mode": "stub"}

    try:
        import requests
        existing = _existing_phones()
        leads    = []
        query    = f"{category} {city} ישראל"

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {"query": query, "language": "he", "key": api_key}

        while len(leads) < _MAX_LEADS:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            for place in data.get("results", []):
                if len(leads) >= _MAX_LEADS:
                    break

                place_id = place.get("place_id", "")
                name     = place.get("name", "")
                address  = place.get("formatted_address", "")

                # Detail call for phone
                phone = ""
                if place_id:
                    time.sleep(_RATE_SEC)
                    d_url = "https://maps.googleapis.com/maps/api/place/details/json"
                    d = requests.get(d_url, params={
                        "place_id": place_id,
                        "fields": "formatted_phone_number",
                        "key": api_key,
                    }, timeout=10).json()
                    phone_raw = d.get("result", {}).get("formatted_phone_number", "")
                    phone = re.sub(r'[-\s]', '', phone_raw)

                # Dedup
                if phone and phone in existing:
                    continue

                lead_data = {
                    "name":     name,
                    "phone":    phone,
                    "address":  address,
                    "category": category,
                    "city":     city,
                    "source":   "maps",
                }
                leads.append(lead_data)
                if phone:
                    existing.add(phone)

            next_token = data.get("next_page_token")
            if not next_token or len(leads) >= _MAX_LEADS:
                break
            params = {"pagetoken": next_token, "key": api_key}
            time.sleep(2.0)

        # Persist leads
        created = _persist_leads(leads)
        _log_session(city, category, len(leads), created)
        return {"leads": leads, "total": len(leads), "created": created, "mode": "live"}

    except Exception as e:
        log.error(f"[LeadScraper] scrape error: {e}", exc_info=True)
        return {"leads": [], "total": 0, "mode": "error", "error": str(e)}


def _persist_leads(leads: list) -> int:
    created = 0
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from engines.lead_engine import compute_score
        repo = LeadRepository()
        for l in leads:
            try:
                lead = repo.create(
                    name=l["name"], phone=l.get("phone", ""),
                    source="maps",
                    notes=f"{l['category']} — {l.get('address','')[:80]}",
                    status="חדש",
                )
                if lead:
                    try:
                        repo.update_score(lead.id, compute_score(lead))
                    except Exception:
                        pass
                    created += 1
            except Exception as e:
                log.debug(f"[LeadScraper] persist error: {e}")
    except Exception as e:
        log.error(f"[LeadScraper] _persist_leads error: {e}")
    return created


def _log_session(city: str, category: str, total: int, created: int) -> None:
    try:
        import pathlib
        sessions_dir = pathlib.Path(__file__).parent.parent.parent / "memory" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        ts    = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
        entry = (f"\n## {ts} UTC — LeadScraper\n"
                 f"- city={city} category={category} found={total} created={created}\n")
        with open(sessions_dir / f"{today}.md", "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass
