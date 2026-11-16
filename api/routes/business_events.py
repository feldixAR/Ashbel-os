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
