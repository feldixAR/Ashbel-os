# Existing business source: read-only daily planning

This opt-in adapter reads the existing Google Sheets CRM, without importing its
rows into PostgreSQL, writing Google cells, contacting people or creating jobs.
The existing daily-plan command, CRM planner and scheduled daily-plan job use the
same projection when enabled. Other engines are not converted or protected by
this change; this is not a claim of a fully synchronized autonomous company.

## Connection

Set these in the hosting platform's secret store, never in code:

- `ASHBEL_SOURCE_CONTEXT_ENABLED=true`
- `ASHBEL_SOURCE_SPREADSHEET_ID`: the verified existing source workbook ID
- `ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON`: a dedicated Google service-account JSON

Enable the Google Sheets API and grant that account **Viewer** access to the
single existing workbook. No domain-wide delegation, Drive scope, Gmail scope or
Editor permission is needed. The adapter requests `spreadsheets.readonly` only,
validates the Google token endpoint, performs one bounded `values:batchGet` and
does not follow provider redirects. OAuth refresh and reads have timeouts.

Ranges and schema are deliberately fixed to the inspected source layout:

- `'לידים'!A1:AE1000`, expected current lead headers including stable lead ID;
- `'תור עבודה'!A1:H50`, stopping at the `מעקבי לידים` section marker before the
  dynamic lead-followup section. It is not counted as a second task queue.

Schema mismatch, missing boundary, duplicate IDs, exhausted lead range, auth or
provider failure produces an unavailable context, never an optimistic empty
business. No cached last-good snapshot is substituted. Update bounds/schema in a
reviewed change if the workbook grows; do not widen ranges blindly.

## Evidence and decisions

Every snapshot contains fetch time, a deterministic content hash, exact source
ranges and row-level evidence. Fetch time does **not** prove that business facts
are current: `source_updated_at=null` and `source_freshness=not_verified` remain
explicit. Repeated reads have no persistent effects or duplicate records.

Rules use `capacity_state=confirmed|blocked|unknown`: lead expansion is allowed
in the daily-plan projection only on an explicit affirmative capacity status;
unknown does not mean available. An active blocking record wins over a positive
record. They hold advanced pricing while showroom/specification selection is
pending. Conflicting actions remain visible with block reasons but are excluded
from proposed daily priorities. These are planning constraints, not execution
permissions. Queue ordering is preserved; this patch makes no claim to intelligent
ranking, date parsing, or comprehensive resolution of Hebrew free text.

Proposal statuses retain source wording; approved draft is not delivery, proposal
value is not collected revenue, and proposed commission is not collected
commission. Unknown financial values are null rather than fabricated zeros.
Only 25 proposal-linked lead facts are projected, without phone/email fields;
unprepared/unpriced defaults are excluded and total/truncated counts are exposed.
Other project history, Drive documents and chat decisions are outside this read.

## Verification and rollback

Synthetic tests cover capacity/spec holds, source provenance, stable fingerprints,
schema failure, duplicate/truncated sources, queue boundary, redacted failures
and integration with the existing planner. No customer fixture is committed.
Live connection is **not verified** until deployed with approved credentials and
observed against the intended workbook. Then test a read, inspect hash/counts and
source rows, test denied access, and confirm no Google writes or outbound actions.

Disable with `ASHBEL_SOURCE_CONTEXT_ENABLED=false` or revert the patch. Disabling
returns the pre-existing daily-plan behavior; that local-DB behavior should not
be represented as the Google CRM source of truth.
