"""Read-only access observation; never stores registry records, CRM data or contacts."""
import hashlib
import json


def inspect():
    from services.integrations.active_construction_source import reviewed_source, parse, verify_primary, FIELDS
    from services.integrations.source_discovery import _fetch
    source = reviewed_source()
    try:
        content = _fetch(source)
        candidates = parse(source, content)
        if any(set(candidate["registry_fact"]) != set(FIELDS) for candidate in candidates):
            raise ValueError("unexpected_registry_fields")
        primary_verified = False
        if candidates:
            candidate = candidates[0]
            verify_primary(candidate, candidate["source_url"], _fetch({**source, "url": candidate["source_url"]}))
            primary_verified = True
        return {"source_status": "observed", "candidate_count": len(candidates),
                "payload_bytes": len(content), "snapshot_sha256": hashlib.sha256(content).hexdigest(),
                "stored_fields": list(FIELDS), "primary_record_readback_verified": primary_verified,
                "crm_appended": 0, "outreach_sent": False, "production_activation": False}
    except Exception as exc:
        # A completed inspection is distinct from a working source connection.
        return {"source_status": "unavailable", "error_code": type(exc).__name__,
                "crm_appended": 0, "outreach_sent": False, "production_activation": False}


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, sort_keys=True))
