# Existing business source: read-only daily planning

This opt-in adapter reads the existing Google Sheets CRM, without importing its
rows into PostgreSQL, writing Google cells, contacting people or creating jobs.
The existing daily-plan command, CRM planner and scheduled daily-plan job use the
same projection when enabled. CEO revenue insights, bottleneck analysis, next
action, report and compound analysis also use this source, without consulting
the local revenue snapshot or daily report. Compound analysis reads one snapshot
rather than combining three potentially different provider reads. Missing source
returns a blocked failed result, not an all-clear or empty-revenue claim. Other
engines are not converted or protected by this change; this is not a claim of a
fully synchronized autonomous company.

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
permissions. Specification holds apply to customer/project tasks; references to
a showroom in supplier or document-management notes do not block supplier work.

Every source task retains its evidence and a disposition: actionable, future,
waiting, needs_review, blocked or completed. Only actionable tasks enter today's
priorities. Explicit ISO or Israeli dates are compared with the snapshot date in
Asia/Jerusalem; future dates do not generate early work recommendations. Pending
showroom/specification work waits unless the task explicitly arranges the visit.
When capacity is unknown/blocked, supplier work is promoted ahead of other
available tasks; remaining available tasks sort by recognized due date and then
source order. Existing follow-ups are not blanket-blocked by capacity.
This is a narrow deterministic projection, not comprehensive Hebrew free-text
understanding, calendar scheduling or a general intelligent ranking engine.

Proposal statuses retain source wording; approved draft is not delivery, proposal
value is not collected revenue, and proposed commission is not collected
commission. Unknown financial values are null rather than fabricated zeros.
Only 25 proposal-linked lead facts are projected, without phone/email fields;
unprepared/unpriced defaults are excluded and total/truncated counts are exposed.
Other project history, Drive documents and chat decisions are outside this read.

## Verification and rollback

Synthetic tests cover capacity/spec scope, supplier priority, future/waiting/review
dispositions, Jerusalem dates, source provenance, stable fingerprints, schema
failure, duplicate/truncated sources, queue boundary, redacted failures and
integration with the existing planner. No customer fixture is committed.
An actual connector-read snapshot was also replayed outside git: this verifies
the projection against the observed layout, not the credentialed adapter or live
provider connection. No customer snapshot is stored in the repository or tests.
Live connection is **not verified** until deployed with approved credentials and
observed against the intended workbook. Then test a read, inspect hash/counts and
source rows, test denied access, and confirm no Google writes or outbound actions.

Disable with `ASHBEL_SOURCE_CONTEXT_ENABLED=false` or revert the patch. Disabling
returns the pre-existing daily-plan behavior; that local-DB behavior should not
be represented as the Google CRM source of truth.
