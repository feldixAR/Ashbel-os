# Durable business-event processing

Opt in with `ASHBEL_BUSINESS_EVENTS_ENABLED=true` and configure the existing
`ASHBEL_SOURCE_CONTEXT_ENABLED` Google source adapter. The existing daily-plan
job ingests source fingerprints and drains the inbox. The existing four-hour
follow-up job drains it too; when enabled it does **not** invoke the legacy
follow-up sender. No new scheduler or ChatGPT automation is created. Existing
source-discovery scanning can run inside daily-plan under its own opt-in flag.

## What actually executes

`DepartmentExpert` instances are registered in the existing agent registry.
Relevant roles run against the current source adapter context and event facts:
sales, engineering, procurement, finance, marketing, strategy, PMO, knowledge.
Each invocation creates an existing `TaskModel` audit record with agent ID,
source references, expected output, result, mode and status. A distinct auditor
expert checks the coordinator's decision. This implementation is explicitly
`native_deterministic`: it does not claim LLM reasoning or external research.
No department sends, purchases, transfers customer material or writes Google.
Finance keeps collected revenue and verified contractor profit unknown without
evidence; historical selling prices are not procurement costs. The strategy
contract uses direct contracting with manufacturing and installation procured
separately. The inbox is event provenance/output, not another lead CRM.

## API and lifecycle

All endpoints require the existing `X-API-Key` authentication, feature flag and
configured business identity:

- `POST /api/business_events/ingest` accepts `source`, `source_event_id`,
  `source_ref`, `event_type`, aware ISO `occurred_at`, and JSON `facts`.
- Types: `opportunity.discovered`, `quote.received`, `supplier.updated`,
  `customer.updated`, `message.received`, `message.status`, `source.snapshot`.
- `POST /api/business_events/process` drains up to 20 ready events.
- `GET /api/business_events` and `GET /api/business_events/<id>` expose evidence,
  task trace, source fingerprint, decision, auditor and writeback disposition.

Identity is unique on business/source/source-event-ID. Same identity and content
returns the original event; conflicting facts return 409. Source occurrence time
is retained from the first intake, but timestamp-only redeliveries do not create
conflicts. Changed source content must use a new event version/ID.

States are pending → processing → analyzed/review_required. `analyzed` means
local analysis and audit persisted, **not** source writeback or business closure.
Unavailable business sources produce blocked status and retry after 15 minutes,
without exhausting processing attempts. Failures retry with bounded backoff and
then dead-letter. Only exception class names are stored, never raw exception
text. Healthy leases are excluded before batch limits, preventing starvation.

Database CAS leases admit one worker per event. Expired leases permit repeating
pure analysis after restart; the old lease cannot commit over a replacement.
A crash on the last allowed attempt becomes dead-letter for review. No outbound
side effect exists inside this replayable critical section. Adding such effects
would require a separate persisted approval/outbox contract, not a callback.

## Migration, verification and limits

An additive `business_event_inbox` table is imported through existing schema
startup; existing tables/rows are not changed. Disable the flag for rollback;
retain the table/audit records. Never drop production data to roll back.

Tests exercise a real persisted inbox, actual registry experts and task records,
six independent processes competing on a shared SQLite file, restart/replay,
stale commits, conflicting versions, tenant boundaries, auth, source failures,
retry/dead-letter, auditor rejection and the actual source adapter projection.
PostgreSQL coordination and live credentials must still be tested after a
controlled deployment. No live source writeback or provider delivery is proved
by these tests. The existing source adapter remains authoritative for reads;
other existing app engines are not all converted to this event runtime.
