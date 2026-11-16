# Existing-source synchronization

This is an opt-in bridge into the existing CRM, not another contact database. Public-feed observations and primary-source reviews use the existing TaskModel queue; the new tables contain only append-operation evidence and a per-workbook lease. No outbound messaging, purchases or commitments are available here.

## Configuration

- ASHBEL_SOURCE_SPREADSHEET_ID: the intended existing workbook. Verify its identity before enabling.
- ASHBEL_SOURCE_CONTEXT_ENABLED=true and ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON: dedicated Viewer credential for source context and preview reads.
- ASHBEL_SOURCE_SYNC_ENABLED=true and ASHBEL_SHEETS_WRITER_SERVICE_ACCOUNT_JSON: **separate** service account explicitly shared as Editor on the intended workbook. Writer credential is never inferred from the Viewer credential.
- ASHBEL_SOURCE_DISCOVERY_ENABLED=true and ASHBEL_PUBLIC_SOURCE_FEEDS_JSON: reviewed public RSS/Atom sources. Each entry requires name, HTTPS url, confirmed_public:true, terms_reviewed:true and allowed_link_hosts.
- No reviewed public feeds are enabled by default. “Not configured” is not a successful scan.

The existing daily maps/source scheduler slot runs the opt-in observer instead of creating another timer. Feed entries remain candidate_unverified in the task queue. The observer never appends to CRM, downloads attachments, follows redirects, authenticates to social networks or obtains contact permission.

## Owner review and append

All endpoints require the existing owner API authentication.

1. GET /api/source_discovery returns candidates with task_id, URL, title, feed-content hash and explicit unverified state.
2. The owner reviews the primary source and exact candidate facts. POST /api/source_discovery/candidates/{task_id}/verify accepts {candidate, review_confirmed:true}. The server fetches fresh primary bytes only from configured public hosts, saves their actual hash, and binds an internally generated verification_id to the exact facts and authenticated review. A client-supplied 64-character hash is not accepted as verification.
3. POST /api/source_sync/preview accepts {candidate} with that verification_id. It reads the existing 44-column schema and checks source key, source URL (including mr.gov.il/www.mr.gov.il aliases), lead ID, normalized phone and name anchored to city against existing rows. A duplicate returns evidence, not a new lead.
4. The preview returns operation_id, preview_hash, row[44] and expiry. POST /api/source_sync/{operation_id}/commit requires the exact preview_hash. It acquires the durable workbook lease, rechecks source changes and duplicates, issues one RAW append with INSERT_ROWS, and reads back the exact new row. Existing cells are never updated. Spreadsheet action dates are numeric date serials.
5. A verified append becomes committed; an opportunity.discovered event is published idempotently. Event-publication failures may retry independently without repeating the append. An approved draft or published contact detail never grants outreach permission.

Candidate facts include source_key, source_url, name, city, project_type, project_stage, aluminum_need, next_action, found_at (required ISO date), published_at (ISO date or empty/null when unknown), quality, confidence, optional entity_type (לקוח/ספק/מתקין/שותף עסקי), phone, email and details. Do not fill unknown facts with invented values. Unknown publication dates remain empty and appear in missing_fields; unverified location/stage/need prevents promotion to a qualified opportunity. Verification expires after 24 hours; unused previews expire after 30 minutes.

## Uncertain outcomes and recovery

A timeout, unexpected provider range, missing readback or interrupted worker does not imply that the append failed. Status remains uncertain/in_flight and the workbook claim blocks further writes. Expiry does not replay a write. POST /api/source_sync/{operation_id}/reconcile performs **only reads**: a single exact matching lead ID and full expected row can reconcile to committed. Missing or ambiguous evidence keeps the claim quarantined for operator investigation. There is deliberately no “retry append” or “clear uncertain” endpoint.

Known before-write read failures and expired unused previews can be prepared again. A changed source needs a fresh preview. Provider/credential error messages are reduced to codes, never raw bodies or secrets.

## Verification limits

Synthetic tests verify protocol, auth, error handling, real separate-process claims and SQL compatibility against disposable SQLite/PostgreSQL services. They do not prove access to the business workbook, active source permissions or deployment. Production activation still requires the scoped credentials, a verified workbook identity, approved public-source configuration and an actual append/readback/event trace. No live credential or customer fixture belongs in Git.
