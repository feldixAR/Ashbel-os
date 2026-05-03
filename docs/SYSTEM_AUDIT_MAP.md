# System Audit Map

## Status

Focused audit update completed on branch `control/alignment-run-2026-05-03`.

This audit is based on direct inspection of key repo files through GitHub. It is not a full local runtime run. Runtime boot, UI rendering and tests still require local or CI execution.

## Code-verified facts

### Repository

- Repo: `feldixAR/Ashbel-os`.
- Working branch for this alignment: `control/alignment-run-2026-05-03`.
- Default production branch from repo metadata/docs: `master`.
- Primary system direction: AshbelOS custom system only.
- HubSpot: out of scope by project decision.

### Runtime and entrypoint

Verified files:

- `Procfile`
- `api/app.py`
- `requirements.txt`
- `.gitignore`

Findings:

- Gunicorn entrypoint is `api.app:create_app()`.
- Procfile command: `gunicorn 'api.app:create_app()' --bind 0.0.0.0:$PORT --workers 2 --timeout 120`.
- Flask app factory exists in `api/app.py`.
- `create_app()` creates a Flask app, configures CORS, calls `create_all_tables()`, bootstraps the event dispatcher, registers blueprints, serves `ui/index.html`, serves `/ui/<path>`, exposes `/api/health`, and attempts to start `scheduler.revenue_scheduler`.
- `requirements.txt` confirms Flask, Gunicorn, SQLAlchemy, PostgreSQL driver, AI provider SDKs, APScheduler, auth/security packages, dotenv, prometheus-client, pytest, flask-cors, requests and httpx.
- `.gitignore` ignores `.env`, local env files, `data/`, local DB files, logs, test caches and IDE folders. This supports keeping real lead files out of Git if they are placed under `data/`.

Status:

- Exists and concrete.
- Requires runtime verification.

### Registered API surface from `api/app.py`

Verified active blueprint imports/registrations include:

- `api.routes.commands`
- `api.routes.actions`
- `api.routes.leads`
- `api.routes.agents`
- `api.routes.tasks`
- `api.routes.approvals`
- `api.routes.reports`
- `api.routes.system`
- `api.routes.goals`
- `api.routes.dashboard`
- `api.routes.learning`
- `api.routes.outreach`
- `api.routes.research`
- `api.routes.delivery`
- `api.routes.analytics`
- `api.routes.crm`
- `api.routes.webhooks`
- `api.routes.briefing`
- `api.routes.admin`
- `api.routes.revenue_queue`
- `api.routes.claude_dispatch`
- `api.routes.gpt_connector`
- `api.routes.mcp`
- `api.routes.openclaw`
- `api.routes.telegram`
- `api.routes.seo`
- `api.routes.lead_ops`
- `api.routes.intake`
- `api.routes.channels`
- `api.routes.whatsapp`

Status:

- Broad API surface exists.
- Some route names are still legacy/generic, including `crm`, but this does not by itself mean external HubSpot dependency.
- Must verify route behavior and whether any route conflicts with the current HubSpot-out decision.

### Health endpoint

Verified in `api/app.py`:

- `/api/health` returns `{"status": "ok"}`, HTTP 200.

Status:

- Exists in code.
- Runtime status not verified in this audit.

### UI entrypoint and shell

Verified files:

- `ui/index.html`
- `ui/js/components/upload_modal.js`

Findings from `ui/index.html`:

- UI is Hebrew RTL: `<html lang="he" dir="rtl">`.
- Title: `AshbelOS — Operating Console`.
- API key modal exists.
- Upload modal exists inside the main UI.
- Operating Console shell exists.
- Header includes profile badge, command input and upload button.
- Command chips exist: hot leads, send queue, meetings, approvals, marketing and document import.
- Today strip exists with metrics for new leads, approvals, manual queue, meetings and pipeline.
- Main work surface tabs: leads, approvals, queue, meetings, growth.
- Intelligence rail exists for agents, learning, Telegram, channels and system changes.
- Mobile bottom navigation exists.
- Scripts loaded: `api.js`, `toast.js`, `ui.js`, `upload_modal.js`, `draft_modal.js`, `shell.js`, `console.js`.

Findings from `upload_modal.js`:

- File upload modal exists.
- Supported extensions in UI: CSV, XLSX, XLS, DOCX, DOC, PDF, TXT.
- Upload posts multipart file to `/api/intake/upload`.
- Review stage groups records by relevant_now, relevant_waiting, missing_info, not_relevant and duplicate.
- Operator can approve, review or skip individual rows.
- Commit posts approved records to `/api/intake/commit`.

Status:

- Import/Upload UI exists.
- RTL and mobile shell exist in markup.
- Runtime visual quality still requires browser verification.
- Commit currently appears to happen directly from the modal after row approval. Need confirm whether this is sufficient approval or whether a separate approval queue is required for full imports.

### Intake API

Verified file:

- `api/routes/intake.py`

Endpoints:

- `POST /api/intake/upload`
- `POST /api/intake/commit`

Findings:

- Upload requires auth.
- Upload accepts multipart file field named `file`.
- Max file size: 10MB.
- Upload uses `skills.document_intelligence.parse_document()`.
- Upload classifies records through `_classify_records()`.
- Preview response includes source file, format, raw count, preview records, group summary and warnings.
- Commit requires auth.
- Commit receives records and source file.
- Commit skips records whose action is `skip` or `reject`.
- Commit calls `engines.lead_acquisition_engine.process_inbound()` to create leads.
- Commit returns created, skipped, errors and lead IDs.

Status:

- Upload and preview exist.
- Commit exists.
- The code describes commit as commit to CRM, but implementation uses AshbelOS internal lead acquisition engine, not external HubSpot.
- Gap: commit is not obviously routed through `ApprovalRepository` or a global import approval request.
- Gap: no explicit ImportRun model/log verified in this audit.
- Gap: no confirmed persisted raw file storage path. The route reads bytes directly from upload.

### Document parser

Verified file:

- `skills/document_intelligence.py`

Findings:

- Stateless parser exists.
- Supported formats documented and implemented: CSV, Excel, Word, PDF and TXT, with graceful fallback where optional packages are unavailable.
- CSV parser uses stdlib csv.
- Excel parser uses optional openpyxl.
- Word parser uses optional python-docx.
- PDF parser uses optional pdfplumber.
- Text parser exists.
- Header mapping supports Hebrew and English fields for name, phone, email, city, company, role and notes.
- Free-text extraction exists for phone and email.

Status:

- Parser exists and is broad.
- Gap: `requirements.txt` does not list `openpyxl`, `python-docx` or `pdfplumber`, so Excel/Word/PDF parsing may fail unless installed in the runtime separately.
- Gap: DOCX support exists in code but dependency may be missing from requirements.

### Lead intelligence

Verified file:

- `skills/lead_intelligence.py`

Findings:

- Normalization contract exists.
- Deduplication contract exists.
- Enrichment contract exists.
- Lead scoring contract exists.
- Ranking and explanation functions exist.
- Israeli phone and email regexes exist.
- City normalization exists for common Israeli cities.
- Role/segment inference exists for architects, interior designers, contractors, developers, project managers and engineers.
- Scoring produces score, priority, reasons and next action.
- Learning-aware scoring adjustment exists through MemoryStore.

Status:

- Lead scoring and next action exist.
- Gap: scoring is generic and may need Ashbel Aluminum-specific work type/project stage/value rules.
- Gap: current document import normalization only maps general fields. It does not yet clearly normalize project stage, work type, budget, proposal readiness fields or import batch.

### Lead operations API

Verified file:

- `api/routes/lead_ops.py`

Endpoints documented in file:

- `POST /api/lead_ops/discover`
- `POST /api/lead_ops/inbound`
- `POST /api/lead_ops/website`
- `GET /api/lead_ops/queue`
- `GET/POST /api/lead_ops/discovery_plan`
- `POST /api/lead_ops/draft`
- `GET /api/lead_ops/status`
- `GET /api/lead_ops/brief/<id>`
- `POST /api/lead_ops/batch_score`
- `POST /api/lead_ops/execute/<approval_id>`
- `POST /api/lead_ops/draft_refine`

Findings:

- Discover pipeline exists.
- Inbound lead processing exists.
- Website analysis exists.
- Work queue exists and splits discovered, inbound, pending_action and meeting_suggestions.
- Draft generation exists.
- Status counts exist.
- AI briefing exists with deterministic fallback.
- Batch scoring exists.
- Execute approval endpoint exists.
- Draft refinement exists.

Status:

- Lead operations are substantial and active in code.
- Gap: proposal readiness not directly verified in this route.
- Gap: daily revenue plan must be verified through revenue routes/modules.
- Gap: `execute` approval endpoint logs approved outreach and emits events, but actual customer-send behavior must be checked in `engines.outreach_engine` and channel services.

### Approval flow

Verified file:

- `api/routes/approvals.py`

Endpoints:

- `GET /api/approvals`
- `GET /api/approvals/history`
- `POST /api/approvals/create`
- `POST /api/approvals/<approval_id>`

Findings:

- Pending approval listing exists.
- Approval history exists.
- UI-created approval request exists.
- Resolve endpoint exists.
- Resolve publishes approval granted/denied events.
- Lead outreach approval logs ActivityModel notes and emits `LEAD_OUTREACH_SENT`.
- System change approvals are stored in MemoryStore.
- Shared `_resolve_approval()` exists for Telegram.

Risk finding:

- For approval details containing `outreach_task`, the approval route can call `execute_outreach(task)`. This must be reviewed to ensure real sending is blocked unless credentials and explicit approval policy allow it.
- For draft-modal style approvals, the code logs approved draft/activity and emits event. That is compatible with controlled manual workflow.

Status:

- Approval system exists.
- Requires safety audit of `engines.outreach_engine` and channel execution modes before approving live use.

### Data safety

Verified `.gitignore`:

- `data/` is ignored.
- `.env` and local env files are ignored.
- DB files and logs are ignored.

Status:

- Good baseline for keeping real lead data out of Git.
- Gap: project needs explicit folder convention and local instructions for `data/raw_leads`, `data/samples`, `data/processed`, `data/import_reports`.

### Tests

Verified file:

- `tests/test_product_fit.py`

Findings:

- Product-fit tests cover profile-driven context, intent routing, queue logic, drafting studio, intake surfaces, SEO workbench and lead-to-action flow.
- Tests confirm draft generation requires approval.
- Tests confirm document column detection in Hebrew and English.
- Tests confirm draft refine endpoint is present in `api/routes/lead_ops.py`.

Status:

- Relevant tests exist.
- Full test suite not run in this audit.
- Additional tests needed for current HubSpot-out decision, full import approval, raw lead folder separation, ImportRun logging and proposal readiness.

## Status summary by area

| Area | Status | Notes |
|---|---|---|
| App entrypoint | Exists | `api.app:create_app()` |
| Production command | Exists | Procfile uses Gunicorn |
| Health endpoint | Exists | Runtime not verified here |
| Custom UI | Exists | Hebrew RTL Operating Console |
| Import UI | Exists | Upload modal and review flow |
| Intake upload | Exists | `/api/intake/upload` |
| Intake preview | Exists | Preview records and group summary |
| Intake commit | Exists but needs approval review | `/api/intake/commit` directly commits approved rows |
| Document parser | Exists | CSV/TXT OK; DOCX/XLSX/PDF need dependency check |
| Lead scoring | Exists | Needs aluminum-specific enrichment check |
| Deduplication | Exists | Phone/email in route, fingerprint skill in skill layer |
| Lead ops | Exists | Discover, inbound, queue, draft, brief, score, execute |
| Approval queue | Exists | Create/list/history/resolve |
| Activity log | Exists in approval flow | Broader import logging not verified |
| Proposal readiness | Unverified | Must audit or implement |
| Daily revenue plan | Unverified in code | Must audit revenue routes/modules |
| HubSpot dependency | Not found in inspected active files | Must search locally in final audit |
| Real data safety | Partially exists | `data/` ignored, but folder convention docs needed |
| Tests | Exist | Full suite not run |

## Required next audit items before implementation

1. Inspect `engines.outreach_engine` and channel services to verify no customer send can bypass approval.
2. Inspect storage models for Lead, Task, Approval, Activity, ImportRun and Proposal readiness.
3. Inspect revenue queue and daily plan implementation.
4. Inspect console JS and API JS for UI behavior and API paths.
5. Inspect scheduler status and learning snapshot.
6. Search for HubSpot references locally and remove/quarantine active direction if present.
7. Run local tests or CI to establish current actual status.
8. Verify UI in browser, especially mobile and Hebrew RTL usability.
9. Verify DOCX dependency and import behavior using a safe sample file.
10. Decide whether `/api/intake/commit` needs a formal ApprovalRepository gate before writing leads.