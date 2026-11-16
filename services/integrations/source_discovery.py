"""Opt-in public-feed observation using the existing task queue and daily job.

Feed entries are unverified candidates. They never become CRM leads or outreach
permission automatically. Only reviewed, explicitly configured public feeds are
contacted; no platform login, scraping bypass, redirects, or social sessions.
"""
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import socket
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from sqlalchemy.exc import IntegrityError
from services.storage.db import get_session
from services.storage.models.task import TaskModel
from services.integrations.source_sync import canonical_url, tenant

TYPE = "public_source_candidate"
KEYWORDS = re.compile(r"אלומיניום|אלומינ|חלונות|ויטרינ|זכוכית|פרזול|מכרז|בניי[הת]|בנייה|alumini?um|glazing|windows|construction|tender", re.I)


def enabled():
    return os.getenv("ASHBEL_SOURCE_DISCOVERY_ENABLED", "").lower() == "true"


def sources():
    value = json.loads(os.getenv("ASHBEL_PUBLIC_SOURCE_FEEDS_JSON", "[]"))
    if not isinstance(value, list) or len(value) > 20:
        raise ValueError("invalid_feed_configuration")
    result = []
    for entry in value:
        if not isinstance(entry, dict) or entry.get("confirmed_public") is not True or entry.get("terms_reviewed") is not True:
            raise ValueError("source_public_access_review_required")
        url = canonical_url(entry.get("url", ""))
        host = urlsplit(url).hostname
        hosts = entry.get("allowed_link_hosts", [host])
        if not isinstance(hosts, list) or len(hosts) > 20 or any(
            canonical_url("https://" + h).split("/")[2] != h for h in hosts
        ):
            raise ValueError("invalid_feed_link_allowlist")
        name = str(entry.get("name", "")).strip()
        if not name or len(name) > 150:
            raise ValueError("invalid_feed_name")
        result.append({"name": name, "url": url, "allowed_link_hosts": hosts})
    return result


def _public_dns(url):
    host = urlsplit(url).hostname
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    values = sorted(set(entry[4][0] for entry in addresses))
    if not values or any(not ipaddress.ip_address(address).is_global for address in values):
        raise ValueError("source_address_not_public")
    return values


def _fetch(source):
    """Pin the checked IP; preserve hostname for Host, SNI and certificate check."""
    import ssl
    import certifi
    import urllib3
    parts = urlsplit(source["url"])
    addresses = _public_dns(source["url"])
    # No second DNS resolution, proxy, redirect, or retry can change this peer.
    pool = urllib3.HTTPSConnectionPool(
        addresses[0], port=443, assert_hostname=parts.hostname,
        server_hostname=parts.hostname, cert_reqs=ssl.CERT_REQUIRED,
        ca_certs=certifi.where(), maxsize=1, block=True,
    )
    response = None
    try:
        path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
        response = pool.request(
            "GET", path,
            headers={"Host": parts.hostname, "User-Agent": "AsifSourceObserver/1.0 (+public-feed-review-only)"},
            timeout=urllib3.Timeout(connect=5, read=15), retries=False, redirect=False,
            preload_content=False,
        )
        if response.status != 200:
            raise ValueError("public_feed_http_" + str(response.status))
        chunks, size = [], 0
        for chunk in response.stream(65536, decode_content=True):
            size += len(chunk)
            if size > 2_000_000:
                raise ValueError("public_feed_too_large")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if response is not None:
            response.close()
        pool.close()


def parse_feed(source, content):
    if not isinstance(content, bytes) or len(content) > 2_000_000 or re.search(br"<!DOCTYPE|<!ENTITY", content, re.I):
        raise ValueError("unsafe_or_oversized_feed")
    root = ET.fromstring(content)
    candidates = []
    for item in list(root.findall(".//item"))[:200] + list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))[:200]:
        def text(*tags):
            for tag in tags:
                node = item.find(tag)
                if node is not None:
                    value = "".join(node.itertext()).strip()
                    if value:
                        return value[:2000]
            return ""
        title = text("title", "{http://www.w3.org/2005/Atom}title")
        description = text("description", "{http://www.w3.org/2005/Atom}summary")
        if not KEYWORDS.search(title + " " + description):
            continue
        link = text("link")
        if not link:
            node = item.find("{http://www.w3.org/2005/Atom}link")
            link = node.get("href", "") if node is not None else ""
        try:
            link = canonical_url(link)
        except ValueError:
            continue
        if urlsplit(link).hostname not in source["allowed_link_hosts"]:
            continue
        candidates.append({
            "status": "candidate_unverified", "title": title, "source_url": link,
            "feed_name": source["name"], "feed_url": source["url"],
            "source_published_text": text("pubDate", "{http://www.w3.org/2005/Atom}published",
                                          "{http://www.w3.org/2005/Atom}updated"),
            "found_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "feed_content_sha256": hashlib.sha256(content).hexdigest(),
            "contact_permission": "unverified", "crm_saved": False,
            "next_action": "Review primary source, relevance, identity and duplicates before CRM preview.",
        })
    return candidates


def _save(candidate):
    task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, tenant() + ":" + candidate["source_url"]))
    task = TaskModel(id=task_id, type=TYPE, action="review_primary_public_source",
                     status="approval_pending", priority=5, model_used="public_feed_parser",
                     input_data={"business_id": tenant(), "source_url": candidate["source_url"],
                                 "external_execution": False}, output_data=candidate)
    try:
        with get_session() as session:
            session.add(task)
            session.flush()
        return True
    except IntegrityError:
        return False


def scan_sources(fetcher=None):
    if not enabled():
        return {"status": "disabled", "crm_appended": 0, "outreach_sent": False}
    configured = sources()
    if not configured:
        return {"status": "not_configured", "sources": [], "crm_appended": 0, "outreach_sent": False}
    fetcher = fetcher or _fetch
    results = []
    for source in configured:
        try:
            candidates = parse_feed(source, fetcher(source))
            count = sum(_save(candidate) for candidate in candidates)
            results.append({"name": source["name"], "status": "observed",
                            "candidate_count": len(candidates), "newly_observed": count})
        except Exception as exc:
            results.append({"name": source["name"], "status": "unavailable",
                            "error_code": type(exc).__name__, "newly_observed": 0})
    status = "observed" if any(r["status"] == "observed" for r in results) else "unavailable"
    return {"status": status, "sources": results,
            "newly_observed": sum(r["newly_observed"] for r in results),
            "crm_appended": 0, "outreach_sent": False}


def list_candidates(limit=30):
    with get_session() as session:
        tasks = session.query(TaskModel).filter(
            TaskModel.type == TYPE, TaskModel.input_data["business_id"].as_string() == tenant(),
        ).order_by(TaskModel.created_at.desc()).limit(min(max(limit, 1), 100)).all()
        return [{"task_id": task.id, **(task.output_data or {})} for task in tasks]


def verify_candidate(task_id, raw, review_confirmed, fetcher=None):
    """Specific owner review + fresh primary bytes, bound to the proposed facts."""
    from services.integrations.source_sync import candidate_fields, digest
    if not enabled():
        raise ValueError("source_discovery_disabled")
    if review_confirmed is not True:
        raise ValueError("specific_source_review_required")
    candidate = candidate_fields(raw)
    with get_session() as session:
        task = session.query(TaskModel).filter_by(id=task_id, type=TYPE).one_or_none()
        if not task or (task.input_data or {}).get("business_id") != tenant():
            raise ValueError("candidate_not_found")
        observation = task.output_data or {}
        if observation.get("source_url") != candidate["source_url"]:
            raise ValueError("source_verification_mismatch")
    configured = next((source for source in sources() if source["url"] == observation.get("feed_url")
                       and urlsplit(candidate["source_url"]).hostname in source["allowed_link_hosts"]), None)
    if not configured:
        raise ValueError("candidate_source_not_configured")
    content = (fetcher or _fetch)({**configured, "url": candidate["source_url"]})
    if not isinstance(content, bytes) or not content or len(content) > 2_000_000:
        raise ValueError("primary_source_unavailable")
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat()
    verification = {
        "method": "owner_verified", "reviewer": "authenticated_owner",
        "source_url": candidate["source_url"], "content_sha256": hashlib.sha256(content).hexdigest(),
        "candidate_hash": digest(candidate), "checked_at": checked_at, "source_candidate_id": task_id,
        "meaning": "Specific owner confirmation of primary-source facts; not outreach permission.",
    }
    verification_id = str(uuid.uuid4())
    with get_session() as session:
        session.add(TaskModel(id=verification_id, type="public_source_review", action="verify_primary_source",
                              status="done", input_data={"business_id": tenant(), "candidate_id": task_id},
                              output_data=verification, approved_by="authenticated_owner",
                              model_used="primary_bytes_and_specific_owner_review", completed_at=checked_at))
        task = session.get(TaskModel, task_id)
        task.output_data = {**observation, "review_status": "owner_verified",
                            "verification_id": verification_id, "crm_saved": False}
    return {"verification_id": verification_id, "verification": verification,
            "candidate": {**candidate, "verification_id": verification_id}, "crm_saved": False}
