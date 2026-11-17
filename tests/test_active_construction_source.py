"""Official public API adapter: scope/privacy/schema and source-bound review."""
import copy
import json
import os
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")

from services.integrations import active_construction_source as registry
from services.integrations import source_discovery as discovery


def payload(rows=None, **changes):
    rows = rows if rows is not None else [dict(work_id=42, site_name='Synthetic project',
        executor_name='Synthetic business', city_name='רעננה', build_types='Synthetic construction')]
    result = {'fields': [{'id': field} for field in registry.FIELDS], 'records': rows, 'total': len(rows)}
    result.update(changes)
    return json.dumps({'success': True, 'result': result}, ensure_ascii=False).encode()


def test_official_query_requests_only_needed_fields_and_all_service_cities():
    source = registry.reviewed_source()
    parts = urlsplit(source['url']); query = parse_qs(parts.query)
    assert parts.scheme == 'https' and parts.netloc == 'data.gov.il'
    assert parts.path == '/api/3/action/datastore_search'
    assert query['resource_id'] == [registry.RESOURCE_ID]
    assert query['fields'] == [','.join(registry.FIELDS)]
    assert 'foreman_name' not in query['fields'][0] and 'executor_id' not in query['fields'][0]
    assert json.loads(query['filters'][0]) == {'city_name': list(registry.CITIES)}
    assert query['limit'] == ['500']


def test_source_configuration_is_locked_and_retains_rss_compatibility(monkeypatch):
    source = registry.reviewed_source()
    monkeypatch.setenv('ASHBEL_PUBLIC_SOURCE_FEEDS_JSON', json.dumps([source]))
    configured = discovery.sources()[0]
    assert configured['type'] == registry.KIND
    for key, value in [('url', 'https://example.com/anything'), ('allowed_link_hosts', ['example.com'])]:
        changed = {**source, key:value}
        monkeypatch.setenv('ASHBEL_PUBLIC_SOURCE_FEEDS_JSON', json.dumps([changed]))
        with pytest.raises(ValueError, match='not_allowlisted'):
            discovery.sources()
    monkeypatch.setenv('ASHBEL_PUBLIC_SOURCE_FEEDS_JSON', json.dumps([
        dict(name='Synthetic RSS', url='https://example.com/feed', confirmed_public=True, terms_reviewed=True)]))
    assert 'type' not in discovery.sources()[0]


def test_records_become_unverified_candidates_not_contacts_and_have_unique_primary_links():
    row = json.loads(payload())['result']['records'][0]
    second = {**row, 'work_id':43}
    candidates = registry.parse(registry.reviewed_source(), payload([row, second]))
    assert len({candidate['source_url'] for candidate in candidates}) == 2
    for candidate in candidates:
        assert candidate['status'] == 'candidate_unverified'
        assert candidate['crm_saved'] is False
        assert candidate['contact_permission'] == 'unverified'
        assert candidate['aluminum_need'] == candidate['project_stage'] == 'not_verified'
        assert 'foreman_name' not in json.dumps(candidate)
        assert set(candidate['registry_fact']) == set(registry.FIELDS)
        query = parse_qs(urlsplit(candidate['source_url']).query)
        assert query['resource_id'] == [registry.RESOURCE_ID]
        assert json.loads(query['filters'][0]) == {'work_id': int(candidate['registry_fact']['work_id'])}
        assert candidate['attribution'].startswith('משרד העבודה')


@pytest.mark.parametrize('mutation', [
    lambda r:r.update(total=501),
    lambda r:r.update(total=2),
    lambda r:r['fields'].append({'id':'foreman_name'}),
    lambda r:r['records'][0].update(foreman_name='must not persist'),
    lambda r:r['records'][0].update(city_name='מחוץ לאזור'),
    lambda r:r['records'][0].update(work_id=True),
    lambda r:r['records'][0].update(site_name=None),
])
def test_schema_privacy_scope_and_truncation_fail_closed(mutation):
    value = json.loads(payload());mutation(value['result'])
    with pytest.raises(ValueError):
        registry.parse(registry.reviewed_source(),json.dumps(value).encode())


def test_primary_review_requires_one_exact_record_and_bound_api_url():
    observation = registry.parse(registry.reviewed_source(), payload())[0]
    registry.verify_primary(observation, observation['source_url'], payload())
    with pytest.raises(ValueError, match='mismatch'):
        registry.verify_primary(observation, 'https://data.gov.il/other', payload())
    wrong = json.loads(payload())['result']['records'][0]; wrong['work_id']=77
    with pytest.raises(ValueError, match='mismatch'):
        registry.verify_primary(observation, observation['source_url'], payload([wrong]))
    with pytest.raises(ValueError):
        registry.verify_primary(observation, observation['source_url'], b'{"success":false}')


def test_scanner_uses_existing_fetch_and_save_without_crm_write(monkeypatch):
    monkeypatch.setenv('ASHBEL_SOURCE_DISCOVERY_ENABLED', 'true')
    monkeypatch.setenv('ASHBEL_PUBLIC_SOURCE_FEEDS_JSON', json.dumps([registry.reviewed_source()]))
    with patch.object(discovery, '_save', return_value=True) as save:
        result = discovery.scan_sources(fetcher=lambda source:payload())
    assert result['status'] == 'observed' and result['newly_observed'] == 1
    assert result['crm_appended'] == 0 and result['outreach_sent'] is False
    assert save.call_args.args[0]['source_kind'] == registry.KIND


def test_ckan_candidate_roundtrip_uses_canonical_primary_url_and_fresh_exact_json(monkeypatch):
    from services.storage.db import create_all_tables, get_session
    from services.storage.models.task import TaskModel
    monkeypatch.setenv('BUSINESS_ID', 'synthetic-registry-roundtrip')
    monkeypatch.setenv('ASHBEL_SOURCE_DISCOVERY_ENABLED', 'true')
    monkeypatch.setenv('ASHBEL_PUBLIC_SOURCE_FEEDS_JSON', json.dumps([registry.reviewed_source()]))
    create_all_tables()
    try:
        result = discovery.scan_sources(fetcher=lambda source: payload())
        assert result['newly_observed'] == 1
        observed = discovery.list_candidates()[0]
        fields = dict(source_key='synthetic-registry-42', source_url=observed['source_url'],
            name='Synthetic project', city='רעננה', project_type='Unverified construction',
            project_stage='לא אומת', aluminum_need='לא אומת', next_action='Review only',
            found_at='2026-11-17', published_at='', quality='unqualified', confidence='source exists')
        response = discovery.verify_candidate(observed['task_id'], fields, True, fetcher=lambda source: payload())
        assert response['verification']['source_url'] == observed['source_url']
        assert response['candidate']['contact_permission'] == 'unverified'
        assert response['crm_saved'] is False
    finally:
        with get_session() as session:
            session.query(TaskModel).filter(TaskModel.input_data['business_id'].as_string() == 'synthetic-registry-roundtrip').delete(synchronize_session=False)
