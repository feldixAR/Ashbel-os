"""Opt-in, internal audit note on an existing CRM work item."""
import json
import os
import re
from urllib.parse import quote

from services.integrations.business_source import WORK_HEADERS, WORK_RANGE, WORK_SECTION_END

SHEETS_SCOPE = 'https://www.googleapis.com/auth/spreadsheets'
SAFE_EVENTS = {'customer.updated', 'quote.received', 'supplier.updated'}


def _blocked(reason):
    return {'status': 'blocked', 'reason': reason}


def _locate(rows, subject):
    if not rows or rows[0][:8] != list(WORK_HEADERS):
        return None
    work = []
    for number, row in enumerate(rows[1:], 2):
        if row and str(row[0]).startswith(WORK_SECTION_END):
            break
        if row:
            work.append((number, row))
    else:
        return None
    matches = [(number, row) for number, row in work if row[0] == subject]
    if len(matches) != 1 or len(matches[0][1]) < 6:
        return None
    number, row = matches[0]
    note = row[5]
    if not isinstance(note, str) or not note.strip() or note.lstrip().startswith('='):
        return None
    if sum(len(other) >= 6 and other[5] == note for _, other in work) != 1:
        return None
    return number, note


def _append_once(read_rows, replace, sheet_id, subject, expected_range, marker, summary):
    original = _locate(read_rows(), subject)
    if original is None:
        return _blocked('work_item_or_note_not_unique')
    row, old = original
    cell = f"'תור עבודה'!F{row}"
    line = f'{marker} {summary}'
    if old.count(marker) == 1 and line in old.splitlines():
        return {'status': 'verified', 'replayed': True, 'cell': cell}
    if marker in old or expected_range != f"'תור עבודה'!A{row}:H{row}":
        return _blocked('work_item_changed')
    new = old + '\n' + line
    if len(new) > 40000:
        return _blocked('work_item_note_too_large')
    changed = replace({
        'find': old, 'replacement': new, 'matchCase': True, 'matchEntireCell': True,
        'searchByRegex': False, 'includeFormulas': False,
        'range': {'sheetId': sheet_id, 'startRowIndex': row - 1, 'endRowIndex': row,
                  'startColumnIndex': 5, 'endColumnIndex': 6},
    })
    if changed not in (0, 1):
        return _blocked('unexpected_write_count')
    verified = _locate(read_rows(), subject)
    if verified and verified[1].count(marker) == 1 and line in verified[1].splitlines():
        return {'status': 'verified', 'replayed': changed == 0,
                'cell': f"'תור עבודה'!F{verified[0]}"}
    return _blocked('writeback_readback_mismatch')


def write_review_note(event, context, decision):
    if (os.getenv('ASHBEL_CRM_WRITEBACK_ENABLED', '').lower() != 'true'
            or event['event_type'] not in SAFE_EVENTS):
        return {'status': 'not_attempted', 'reason': 'read_only_runtime'}
    approved_source = os.getenv('ASHBEL_CRM_WRITEBACK_SOURCE', '').strip()
    workbook = os.getenv('ASHBEL_SOURCE_SPREADSHEET_ID', '').strip()
    sheet_id = os.getenv('ASHBEL_CRM_WORK_SHEET_ID', '').strip()
    raw = os.getenv('ASHBEL_CRM_WRITEBACK_SERVICE_ACCOUNT_JSON')
    if not approved_source or event['source'] != approved_source:
        return _blocked('event_source_not_allowed')
    if (not re.fullmatch(r'[A-Za-z0-9_-]{20,150}', workbook) or workbook != context.get('spreadsheet_id')
            or not re.fullmatch(r'[0-9]{1,10}', sheet_id) or not raw):
        return _blocked('crm_writer_not_configured')
    item = (decision.get('next_action') or {}).get('work_item')
    if not item or item.get('disposition') == 'completed':
        return _blocked('no_existing_open_work_item')
    if not re.fullmatch(r'[0-9a-f]{64}', event['fingerprint']):
        return _blocked('invalid_event_fingerprint')

    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials

    info = json.loads(raw)
    if info.get('type') != 'service_account' or info.get('token_uri') != 'https://oauth2.googleapis.com/token':
        return _blocked('invalid_writer_credentials')
    marker = f"[ashbel-event:{event['fingerprint']}]"
    kind = ('עדכון לקוח' if event['event_type'] == 'customer.updated' else
            'עדכון רכש פנימי' if event['event_type'] == 'supplier.updated' else 'קליטת הצעה')
    summary = f'{kind} עבר בדיקה פנימית. המשך בהתאם לפעולה ולמועד ברשומה.'
    if review := decision.get('supplier_review'):
        manufacturing, market = review['manufacturing'], review['market']
        installation_low, installation_high = review['installation']
        cost_low, cost_high = review['scenario']['manufacturing_plus_installation']
        gap_low, gap_high = review['scenario']['gap_before_other_costs']
        summary = (
            f"בדיקת ספקים פנימית (₪ לפני מע״מ). ייצור בעל פה {manufacturing['oral_ils_ex_vat']:,}, "
            f"פתיחה {manufacturing['opening_ils_ex_vat']:,}, אומדן {manufacturing['estimate_ils_ex_vat']:,}. "
            f"פער {manufacturing['estimate_gap_pct']:.1f}%, יחס {manufacturing['calibration_ratio_only']:.3f} לכיול בלבד. "
            f"התקנה באומדן {installation_low:,}–{installation_high:,}, יחד {cost_low:,}–{cost_high:,}. "
            f"השוואות מכירה {market['market_quote']:,} ו־{market['market_floor']:,}, תכולה טרם אומתה. "
            f"בתרחיש מכירה {market['scenario_sale']:,}, פער {gap_low:,}–{gap_high:,} לפני יתר העלויות. "
            f"החלטה: {decision['summary']}"
        )
    if event['source_ref'] == 'ashbelos:owner-console':
        owner_update = event['facts'].get('owner_update')
        if (not isinstance(owner_update, str) or not 1 <= len(owner_update) <= 1800
                or len(owner_update.splitlines()) != 1 or '[ashbel-event:' in owner_update.lower()):
            return _blocked('invalid_owner_update')
        summary = f'עדכון בעלים: {owner_update} | החלטת מנכ״ל: {decision["summary"]}'
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{workbook}'
    work_range = quote(WORK_RANGE, safe='')
    credentials = Credentials.from_service_account_info(info, scopes=[SHEETS_SCOPE])
    with AuthorizedSession(credentials) as session:
        response = session.get(url, params={'fields': 'sheets.properties(sheetId,title)'},
                               timeout=(5, 15), allow_redirects=False)
        response.raise_for_status()
        target = [sheet.get('properties', {}).get('sheetId') for sheet in response.json().get('sheets', [])
                  if sheet.get('properties', {}).get('title') == 'תור עבודה']
        if target != [int(sheet_id)]:
            return _blocked('work_sheet_id_mismatch')

        def read_rows():
            response = session.get(f'{url}/values/{work_range}',
                                   params={'valueRenderOption': 'FORMULA'},
                                   timeout=(5, 15), allow_redirects=False)
            response.raise_for_status()
            return response.json().get('values', [])

        def replace(request):
            response = session.post(f'{url}:batchUpdate', json={'requests': [{'findReplace': request}]},
                                    timeout=(5, 15), allow_redirects=False)
            response.raise_for_status()
            replies = response.json().get('replies') or [{}]
            return replies[0].get('findReplace', {}).get('occurrencesChanged', 0)

        return _append_once(read_rows, replace, int(sheet_id), item['subject'],
                            item.get('evidence', {}).get('range'), marker, summary)
