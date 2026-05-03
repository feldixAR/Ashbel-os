# Full System Audit 2026-05-03

## Scope

This audit aligns AshbelOS with the current product definition: Ashbel Aluminum daily revenue operating system, not a generic CRM. It focuses on production readiness, import flow, browser review, UI clarity and safety.

## Audit result summary

| Area | Exists | Works | Matches scope | Risk | Notes |
|---|---:|---:|---:|---|---|
| App boot and entrypoint | Yes | Production reported OK | Yes | Low | `api.app:create_app()` and `/api/health` exist. |
| Health endpoint | Yes | Production reported HTTP 200 | Yes | Low | Wrapped response includes DB status. |
| Auth/API key | Yes | Fixed for upload UI | Yes | Medium | FormData upload now uses the same Ashbel API key helper as regular API calls. |
| Main UI | Yes | Production loaded | Partial | Medium | UI exists but still needs browser walkthrough for clarity. |
| Import Center | Yes | UI error handling fixed | Partial | High | Generic hidden backend errors were fixed in UploadModal. |
| CSV import | Yes | Expected to work after UI key fix | Yes | Medium | Previous CSV failure was likely caused by upload auth/header mismatch. |
| DOCX import | Yes | Generic only | Partial | High | Dedicated Bonim Israel parser helper was added but could not yet be connected to the active parser due update-tool blocking. |
| Lead normalization | Yes | Partial | Partial | Medium | Generic normalization exists. Bonim helper maps stage, city, owner, phone, email, notes and aluminum work type. |
| Lead scoring | Yes | Existing | Partial | Medium | Scoring exists. Business scoring still needs browser review with real workflow. |
| Next action logic | Yes | Existing | Partial | Medium | Existing score output includes next action. |
| Proposal readiness | Yes | Existing | Partial | Medium | Existing readiness surfaced. Needs browser walkthrough. |
| Approval Gate | Yes | Existing | Yes | Medium | Import commit and outreach are approval gated by previous run. |
| Activity log | Yes | Existing | Partial | Medium | Import and lead-change logs exist in code. |
| Daily Revenue Plan | Yes | Existing | Partial | Medium | Queue endpoint exists. Must be checked after imported test lead. |
| Draft generation | Yes | Existing | Yes | Medium | Drafts require approval. No direct send in safe flow. |
| Outreach safety | Yes | Existing | Yes | Low | Draft-only or approval-required paths exist. |
| WhatsApp/email blocked | Yes | Existing | Yes | Low | Direct sends remain blocked or approval-required. |
| Mobile RTL UI | Yes | Not fully verified | Partial | Medium | Markup is RTL. Browser/mobile review still needed. |
| Empty/loading/error states | Yes | Partial | Partial | Medium | Import error display improved. Full UX pass still required. |
| HubSpot absence | Yes | Reported absent | Yes | Low | HubSpot out of scope. |
| QA Console | Added | Requires production deploy/browser check | Yes | Low | New read-only `/api/system/qa` plus browser panel. |

## Critical mismatches found

1. Upload UI hid the real backend error because the API contract uses `error`, while the UI read only `res.data?.message` or `res.message`.
2. FormData upload did not reliably use the current AshbelOS API key because `API._getKey` was not exposed, and the fallback used old keys.
3. DOCX parsing was generic and did not support the actual Bonim Israel Word lead format.
4. There was no browser-facing QA panel for quick operator walkthrough.

## Fixes applied

1. Exposed `API._getKey()` and added `API.systemQa()`.
2. Updated `UploadModal` to show `res.error` and to use the correct Ashbel API key for FormData uploads.
3. Added Bonim Israel parser helper module.
4. Added read-only system QA endpoint: `GET /api/system/qa`.
5. Added browser QA panel injected into the existing UI as `בדיקת מערכת`.

## Not fully completed

The dedicated Bonim Israel parser helper exists, but the active `skills/document_intelligence.py` file was not changed because the GitHub update tool blocked that large parser update twice. The correct next fix is to connect `document_intelligence.py` to `skills.bonim_israel_parser` inside CSV, Word, PDF and text parsing paths.

## Safety status

- No real lead import performed by this audit.
- No customer contact performed.
- No WhatsApp or Email sent.
- QA endpoint is read-only.
- No secrets or real lead files added.

## Next browser walkthrough

1. Open production UI.
2. Confirm the new `בדיקת מערכת` chip appears.
3. Open it and verify API/DB/parser/approval checks load.
4. Open `יבוא מסמך`.
5. Upload a small synthetic CSV.
6. Confirm Preview appears and no real commit happens.
7. Upload the Word file only after parser connection is completed.
8. Approve only synthetic records.
9. Confirm daily revenue plan and proposal readiness.
10. Confirm no outreach was sent.
