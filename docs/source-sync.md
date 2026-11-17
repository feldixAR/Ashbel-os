# Existing-source synchronization

This is an opt-in bridge into the existing CRM, not another contact database. Public-feed observations and primary-source reviews use the existing TaskModel queue; the new tables contain only append-operation evidence and a per-workbook lease. No outbound messaging, purchases or commitments are available here.

## Configuration

- ASHBEL_SOURCE_SPREADSHEET_ID: the intended existing workbook. Verify its identity before enabling.
- ASHBEL_SOURCE_CONTEXT_ENABLED=true and ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON: dedicated Viewer credential for source context and preview reads.
- ASHBEL_SOURCE_SYNC_ENABLED=true and ASHBEL_SHEETS_WRITER_SERVICE_ACCOUNT_JSON: **separate** service account explicitly shared as Editor on the intended workbook. Writer credential is never inferred from the Viewer credential.
- ASHBEL_SOURCE_DISCOVERY_ENABLED=true and ASHBEL_PUBLIC_SOURCE_FEEDS_JSON: reviewed public RSS/Atom sources. Each entry requires name, HTTPS url, confirmed_public:true, terms_reviewed:true and allowed_link_hosts.
- Connections pin the checked public IP while validating the original hostname through TLS SNI/certificate/Host; DNS rebinding, proxies, redirects and automatic connection retries cannot change that peer.

No reviewed public feeds are enabled by default. “Not configured” is not a successful scan.

Legacy scheduled Gmail/Maps intake and outreach are disabled unless the specific
`ASHBEL_LEGACY_SCHEDULED_INTAKE_ENABLED` or
`ASHBEL_LEGACY_SCHEDULED_OUTREACH_ENABLED` opt-in is true. Any active company
source/event/pricing component still blocks those legacy paths. Existing manual
authenticated operations keep their approval contracts.

## Pricing source events

Enable `ASHBEL_PRICING_SOURCE_ENABLED=true` with an explicit
`ASHBEL_PRICING_SPREADSHEET_ID` for the existing pricing workbook. The same
dedicated Viewer service account must have Viewer access to that workbook.
`'מחירי מקור'!A4:T2000` is read with exact schema and unformatted values;
content-stable quote events are ingested through the existing daily plan and
governed follow-up/poll paths. Changed source content yields a new event while
unchanged reads deduplicate. Included lines and alternatives remain separate;
unknown values remain null. A sum of source rows is not verification of the
PDF grand total, a signed contract, procurement cost, profit or collection.

The existing daily maps/source scheduler slot runs the opt-in observer instead of creating another timer. In governed company/source mode, disabled discovery and Gmail intake never fall back to legacy local-CRM imports. Feed entries remain candidate_unverified in the task queue. The observer never appends to CRM, downloads attachments, follows redirects, authenticates to social networks or obtains contact permission.

## Owner review and append

All endpoints require the existing owner API authentication.

1. GET /api/source_discovery returns candidates with task_id, URL, title, feed-content hash and explicit unverified state.
2. The owner reviews the primary source and exact candidate facts. POST /api/source_discovery/candidates/{task_id}/verify accepts {candidate, review_confirmed:true}. The server fetches fresh primary bytes only from configured public hosts, saves their actual hash, and binds an internally generated verification_id to the exact facts and authenticated review. A client-supplied 64-character hash is not accepted as verification.
3. POST /api/source_sync/preview accepts {candidate} with that verification_id. It reads the existing 44-column schema and checks source key, source URL (including mr.gov.il/www.mr.gov.il aliases), lead ID, normalized phone and name anchored to city against existing rows. A duplicate returns evidence, not a new lead.
4. The preview returns operation_id, preview_hash, row[44] and expiry. POST /api/source_sync/{operation_id}/commit requires the exact preview_hash. It acquires the durable workbook lease, rechecks source changes and duplicates, issues one RAW append with INSERT_ROWS, and reads back the exact new row. Existing cells are never updated. Spreadsheet action dates are numeric date serials.
5. A verified append becomes committed; an opportunity.discovered event is published idempotently. Event-publication failures are persisted in the operation journal and retried by the existing governed follow-up job, independently without repeating the append. Reconciliation also publishes the event. An approved draft or published contact detail never grants outreach permission.

Candidate facts include source_key, source_url, name, city, project_type, project_stage, aluminum_need, next_action, found_at (required ISO date), published_at (ISO date or empty/null when unknown), quality, confidence, optional entity_type (לקוח/ספק/מתקין/שותף עסקי), phone, email and details. Do not fill unknown facts with invented values. Unknown publication dates remain empty and appear in missing_fields; unverified location/stage/need prevents promotion to a qualified opportunity. Verification expires after 24 hours; unused previews expire after 30 minutes.

## Uncertain outcomes and recovery

A timeout, unexpected provider range, missing readback or interrupted worker does not imply that the append failed. Status remains uncertain/in_flight and the workbook claim blocks further writes. Expiry does not replay a write. POST /api/source_sync/{operation_id}/reconcile performs **only reads**: a single exact matching lead ID and full expected row can reconcile to committed. Missing or ambiguous evidence keeps the claim quarantined for operator investigation. There is deliberately no “retry append” or “clear uncertain” endpoint.

Known before-write read failures and expired unused previews can be prepared again. A changed source needs a fresh preview. Provider/credential error messages are reduced to codes, never raw bodies or secrets.

## Verification limits

Synthetic tests verify protocol, auth, error handling, real separate-process claims and SQL compatibility against disposable SQLite/PostgreSQL services. They do not prove access to the business workbook, active source permissions or deployment. Production activation still requires the scoped credentials, a verified workbook identity, approved public-source configuration and an actual append/readback/event trace. No live credential or customer fixture belongs in Git.

## Official construction registry source (reviewed 2026-11-17)

`config/public_sources.example.json` contains one ready configuration for the
Ministry of Labor **active construction sites** resource on data.gov.il. Use its
JSON value for `ASHBEL_PUBLIC_SOURCE_FEEDS_JSON` with the existing opt-in
`ASHBEL_SOURCE_DISCOVERY_ENABLED=true`. This reuses the existing source scanner
and its scheduled slot; no extra scheduler or CRM is created.

- Official resource: `b072e36c-a53b-49e1-be08-4a608fcf4638`, package
  `bddf37d6-5300-4179-bc0b-f2577fbc3a30`.
- Source metadata: `https://data.gov.il/api/3/action/resource_show?id=b072e36c-a53b-49e1-be08-4a608fcf4638`.
  Its package reports `license_id=other-open`, no separate license URL.
- The official portal's current license at
  `https://data.gov.il/terms-of-use` permits commercial and noncommercial reuse,
  requires source attribution, and excludes privacy-infringing use. The portal
  describes automated API access at `https://data.gov.il/about`.
- Only the fixed `datastore_search` endpoint/resource is allowed. Requests
  select `work_id,site_name,executor_name,city_name,build_types` and the existing
  twenty service areas (including the official Binyamina–Givat Ada name).
  Foreman names, IDs, sanctions and contact data are not requested or stored.
- Schema changes, unexpected fields/cities, missing records and a response above
  the bounded 500-record regional limit block ingestion rather than silently
  claiming complete coverage. TLS/IP pinning, byte bounds and no redirects or
  retries are inherited from the existing scanner.
- A live read on the review date returned HTTP200, 182 regional records and the
  five expected fields. These are public registry **candidates**, not 182 leads,
  not evidence of an open aluminum requirement, not a verified building stage,
  and never permission to contact anyone. No live records are committed as
  fixtures or used to enrich private identities.
- Each candidate retains Ministry of Labor/data.gov.il attribution and a
  source URL that queries its exact `work_id`. Specific review re-fetches that
  bounded primary JSON and verifies the exact record before normal CRM preview.
  Publication date remains unknown because this resource has no per-project
  publication timestamp. Snapshot freshness is not project freshness.

The scanner remains optional. It does not automatically append these observations
to the CRM or send outreach. A source becoming unavailable is a source error,
not an empty successful scan or proof that no projects exist.
