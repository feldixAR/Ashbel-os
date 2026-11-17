"""Minimal official CKAN source: public construction facts, never qualified leads.

Only this reviewed resource, five requested fields and the existing service
cities are accepted. Personal foreman names, IDs, sanctions and contact data are
neither requested nor persisted. No private-source joins or contact permission.
"""
import datetime as dt
import hashlib
import json
import re
from urllib.parse import urlencode

API_URL = 'https://data.gov.il/api/3/action/datastore_search'
RESOURCE_ID = 'b072e36c-a53b-49e1-be08-4a608fcf4638'
FIELDS = ('work_id', 'site_name', 'executor_name', 'city_name', 'build_types')
CITIES = ('שערי תקווה', 'אורנית', 'פדואל', 'עלי זהב', 'יקיר', 'נופים', 'אריאל',
          'רחלים', 'תפוח', 'מגדלים', 'עלי', 'קרני שומרון', 'אלפי מנשה', 'קדומים',
          'עץ אפרים', 'ראש העין', 'צופים', 'בנימינה', 'בנימינה-גבעת עדה', 'בית אריה', 'רעננה')
LIMIT = 500
KIND = 'ckan_active_sites'


def query_url(filters, limit):
    return API_URL + '?' + urlencode({'resource_id': RESOURCE_ID, 'fields': ','.join(FIELDS),
                                      'filters': json.dumps(filters, ensure_ascii=False, sort_keys=True,
                                                            separators=(',', ':')),
                                      'limit': limit, 'sort': 'work_id asc'})


SOURCE_URL = query_url({'city_name': list(CITIES)}, LIMIT)


def work_id(value):
    if isinstance(value, bool):
        raise ValueError('invalid_registry_work_id')
    if isinstance(value, int) and value > 0:
        return str(value)
    if isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{0,17}', value):
        return value
    raise ValueError('invalid_registry_work_id')


def primary_url(identifier):
    return query_url({'work_id': int(work_id(identifier))}, 1)


def payload_records(content, limit=LIMIT):
    if not isinstance(content, bytes) or not content or len(content) > 2_000_000:
        raise ValueError('invalid_registry_payload')
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeError):
        raise ValueError('invalid_registry_payload') from None
    if not isinstance(payload, dict) or payload.get('success') is not True:
        raise ValueError('registry_request_unsuccessful')
    result = payload.get('result')
    if not isinstance(result, dict):
        raise ValueError('registry_schema_changed')
    fields = result.get('fields')
    if not isinstance(fields, list) or len(fields) != len(FIELDS) or any(
        not isinstance(field, dict) for field in fields
    ) or {field.get('id') for field in fields} != set(FIELDS):
        raise ValueError('registry_schema_changed')
    records, total = result.get('records'), result.get('total')
    if not isinstance(records, list) or isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ValueError('registry_schema_changed')
    if total > limit:
        # Do not silently describe a truncated query as complete coverage.
        raise ValueError('registry_scope_requires_pagination')
    if len(records) != total or len(records) > limit:
        raise ValueError('registry_incomplete_response')
    clean, identities = [], set()
    for row in records:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError('registry_unexpected_fields')
        identifier = work_id(row['work_id'])
        if identifier in identities:
            raise ValueError('registry_duplicate_work_id')
        identities.add(identifier)
        if any(not isinstance(row[key], str) or len(row[key]) > 1500 for key in FIELDS[1:]):
            raise ValueError('registry_schema_changed')
        # Provider-side filtering is checked again locally.
        if row['city_name'].strip() not in CITIES:
            raise ValueError('registry_city_outside_scope')
        clean.append({**row, 'work_id': identifier})
    return clean


def parse(source, content):
    from services.integrations.source_sync import canonical_url
    rows = payload_records(content)
    found = dt.datetime.now(dt.timezone.utc).isoformat()
    return [{
        'status': 'candidate_unverified',
        'title': 'אתר בנייה פעיל — ' + row['city_name'].strip() + ' — ' + row['site_name'].strip(),
        'source_url': canonical_url(primary_url(row['work_id'])), 'feed_name': source['name'],
        'feed_url': canonical_url(source['url']),
        'source_kind': KIND, 'source_published_text': '', 'found_at': found,
        'feed_content_sha256': hashlib.sha256(content).hexdigest(),
        'registry_fact': row, 'attribution': 'משרד העבודה · data.gov.il · אתרי בנייה פעילים',
        'contact_permission': 'unverified', 'crm_saved': False,
        'aluminum_need': 'not_verified', 'project_stage': 'not_verified',
        'next_action': 'Verify project relevance, aluminum need, stage and lawfully published business contact details; no outreach permission.',
    } for row in rows]


def verify_primary(observation, candidate_url, content):
    from services.integrations.source_sync import canonical_url
    identifier = work_id((observation.get('registry_fact') or {}).get('work_id'))
    if canonical_url(candidate_url) != canonical_url(primary_url(identifier)):
        raise ValueError('source_verification_mismatch')
    rows = payload_records(content, limit=1)
    if len(rows) != 1 or rows[0]['work_id'] != identifier:
        raise ValueError('source_verification_mismatch')


def reviewed_source():
    return {'type': KIND, 'name': 'משרד העבודה — אתרי בנייה פעילים באזורי אסיף',
            'url': SOURCE_URL, 'allowed_link_hosts': ['data.gov.il'],
            'confirmed_public': True, 'terms_reviewed': True}
