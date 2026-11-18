from unittest.mock import Mock

import pytest

from services.integrations.business_source import WORK_HEADERS, WORK_SECTION_END
from services.integrations.crm_writeback import _append_once, write_review_note


@pytest.fixture
def workbook():
    rows = [list(WORK_HEADERS), ['customer', 'action', 'date', 'open', 'owner', 'old note'],
            [WORK_SECTION_END]]

    def replace(request):
        assert request['matchEntireCell'] and not request['includeFormulas']
        assert request['range'] == {'sheetId': 12, 'startRowIndex': 1, 'endRowIndex': 2,
                                    'startColumnIndex': 5, 'endColumnIndex': 6}
        if rows[1][5] != request['find']:
            return 0
        rows[1][5] = request['replacement']
        return 1

    return rows, Mock(side_effect=replace)


def run(rows, replace):
    return _append_once(lambda: rows, replace, 12, 'customer', "'תור עבודה'!A2:H2",
                        '[event:abcdef]', 'reviewed')


def test_writes_one_existing_note_and_replay_is_read_only(workbook):
    rows, replace = workbook
    assert run(rows, replace) == {'status': 'verified', 'replayed': False, 'cell': "'תור עבודה'!F2"}
    assert run(rows, replace)['replayed'] is True
    replace.assert_called_once()
    assert rows[1][1:5] == ['action', 'date', 'open', 'owner']


@pytest.mark.parametrize('change', ('duplicate', 'formula', 'moved', 'no_boundary'))
def test_unsafe_target_is_never_replaced(workbook, change):
    rows, replace = workbook
    if change == 'duplicate':
        rows.insert(2, ['other', '', '', '', '', 'old note'])
    elif change == 'formula':
        rows[1][5] = '=TEXT(TODAY(),"dd")'
    elif change == 'moved':
        rows.insert(1, ['another'])
    else:
        rows.pop()
    assert run(rows, replace)['status'] == 'blocked'
    replace.assert_not_called()


def test_lost_response_after_write_is_reconciled_without_second_write(workbook):
    rows, replace = workbook

    def commit_then_lose(request):
        replace(request)
        raise TimeoutError

    with pytest.raises(TimeoutError):
        run(rows, commit_then_lose)
    assert run(rows, replace)['replayed'] is True
    replace.assert_called_once()


def test_provider_count_without_readback_never_verifies(workbook):
    rows, _ = workbook
    assert run(rows, Mock(return_value=1))['reason'] == 'writeback_readback_mismatch'


def test_denies_unconfigured_and_unapproved_sources_before_transport(monkeypatch):
    event = {'event_type': 'quote.received', 'source': 'not-approved'}
    monkeypatch.delenv('ASHBEL_CRM_WRITEBACK_ENABLED', raising=False)
    assert write_review_note(event, {}, {})['status'] == 'not_attempted'
    monkeypatch.setenv('ASHBEL_CRM_WRITEBACK_ENABLED', 'true')
    monkeypatch.setenv('ASHBEL_CRM_WRITEBACK_SOURCE', 'internal-source')
    assert write_review_note(event, {}, {}) == {'status': 'blocked', 'reason': 'event_source_not_allowed'}
    assert write_review_note({**event, 'event_type': 'message.received'}, {}, {})['status'] == 'not_attempted'
