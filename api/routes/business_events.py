"""Authenticated durable-event intake/status/process. No outbound effects."""
from flask import Blueprint, request
from api.middleware import require_auth, ok, _error

bp = Blueprint('business_events', __name__)


def _enabled():
    from services.business_events.runtime import enabled
    return enabled()


@bp.route('/business_events', methods=['GET'])
@require_auth
def list_events():
    if not _enabled():
        return _error('business_events_disabled', 503)
    from services.business_events.runtime import recent_events
    return ok({'events': recent_events()})


@bp.route('/business_events/<event_id>', methods=['GET'])
@require_auth
def read_event(event_id):
    if not _enabled():
        return _error('business_events_disabled', 503)
    from services.business_events.runtime import get_event
    event = get_event(event_id)
    return ok({'event': event}) if event else _error('event_not_found', 404)


@bp.route('/business_events/ingest', methods=['POST'])
@require_auth
def ingest():
    if not _enabled():
        return _error('business_events_disabled', 503)
    if request.content_length and request.content_length > 65536:
        return _error('event_too_large', 413)
    from services.business_events.runtime import ingest_event
    try:
        result = ingest_event(request.get_json(silent=True))
        return ok(result, 200 if result['duplicate'] else 201)
    except ValueError as exc:
        return _error(str(exc), 409 if str(exc) == 'source_event_conflict' else 400)
    except Exception:
        return _error('event_storage_unavailable', 503)


@bp.route('/business_events/process', methods=['POST'])
@require_auth
def process():
    if not _enabled():
        return _error('business_events_disabled', 503)
    from services.business_events.runtime import process_pending
    try:
        return ok({'results': process_pending()})
    except Exception:
        return _error('event_storage_unavailable', 503)


@bp.route('/business_events/contracts', methods=['GET'])
@require_auth
def contracts():
    from services.business_events.departments import ROLES, role_contract
    return ok({'contracts': [role_contract(role) for role in ROLES],
               'runtime_enabled': _enabled(), 'execution_mode': 'native_deterministic'})


@bp.route('/business_events/poll', methods=['POST'])
@require_auth
def poll():
    if not _enabled():
        return _error('business_events_disabled', 503)
    from services.business_events.runtime import poll_source_and_process
    try:
        result = poll_source_and_process()
        return ok(result)
    except Exception:
        return _error('event_storage_unavailable', 503)


@bp.route('/business_events/work_items', methods=['GET'])
@require_auth
def work_items():
    if not _enabled():
        return _error('business_events_disabled', 503)
    from services.business_events.work_items import list_work_items
    try:
        limit = int(request.args.get('limit', 50))
        return ok({'items': list_work_items(limit), 'source_queue_is_authoritative': True})
    except ValueError:
        return _error('invalid_limit', 400)
    except Exception:
        return _error('work_item_storage_unavailable', 503)


@bp.route('/business_events/work_items/<item_id>/review', methods=['POST'])
@require_auth
def review_work_item(item_id):
    if not _enabled():
        return _error('business_events_disabled', 503)
    if request.content_length and request.content_length > 8192:
        return _error('review_too_large', 413)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error('invalid_review', 400)
    from services.business_events.work_items import review_work_item as review
    try:
        return ok({'item': review(item_id, body.get('action'), body.get('expected_version'),
                                  body.get('note'), body.get('evidence_ref', '')),
                   'external_action_executed': False})
    except LookupError:
        return _error('work_item_not_found', 404)
    except ValueError as exc:
        return _error(str(exc), 409 if str(exc) == 'work_item_version_conflict' else 400)
    except Exception:
        return _error('work_item_storage_unavailable', 503)
