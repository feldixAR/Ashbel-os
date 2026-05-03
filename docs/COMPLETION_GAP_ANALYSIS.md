# Completion Gap Analysis

## Status

Focused audit update completed on branch `control/alignment-run-2026-05-03`.

This analysis is based on targeted file inspection. It is not a runtime proof. Final implementation must still include local tests and UI verification.

## Strategic status

Good news: the existing `Ashbel-os` repo already contains much more than a basic CRM. It has the app entrypoint, custom RTL UI, upload/import modal, document parsing, lead intelligence, lead operations, approvals, drafts, GPT/MCP/Telegram routes and a broad production-oriented structure.

Main issue: the system must be tightened into a safe daily working system, with clear internal import approval, real lead data handling, proposal readiness, daily revenue proof and no HubSpot direction.

## Must-have gaps before final daily use

### 1. Runtime verification

Status: open.

Required:

- Run local boot.
- Verify `/api/health`.
- Verify UI opens.
- Verify app can register all blueprints.
- Run relevant tests.
- Later verify production only after local confidence.

### 2. Import approval hardening

Status: open.

Finding:

- `/api/intake/upload` already produces preview.
- `upload_modal.js` lets the operator approve rows and call `/api/intake/commit`.
- `/api/intake/commit` directly creates leads through `process_inbound()` for approved rows.

Gap:

- Need decide and implement whether import commit must go through `ApprovalRepository` before writing to DB, especially for full file imports.
- Required policy: preview first, then approval, then internal commit.
- Large or full imports should require a formal approval ID.

### 3. ImportRun and Activity logging

Status: open.

Finding:

- ActivityModel is used in approval/outreach flows.
- No ImportRun model/log was verified in focused audit.

Required:

- Add or verify ImportRun logging.
- Record source file, raw count, approved count, created, skipped, duplicates, errors and operator.
- Record import commit in Activity Log or a dedicated import report.

### 4. Real lead data folder convention

Status: open.

Finding:

- `.gitignore` ignores `data/`, which is good for private lead files.

Required:

- Establish folders outside Git tracking:
  - `data/raw_leads`
  - `data/samples`
  - `data/processed`
  - `data/import_reports`
- Document exactly where to put real files.
- Ensure samples cannot be treated as real data.

### 5. DOCX/XLSX/PDF dependency gap

Status: open.

Finding:

- `skills/document_intelligence.py` supports Word, Excel and PDF through optional libraries.
- `requirements.txt` does not include `python-docx`, `openpyxl` or `pdfplumber`.

Required:

- Decide supported production formats.
- At minimum, add `python-docx` if DOCX lead files are expected.
- Add `openpyxl` only if XLSX is required.
- Add `pdfplumber` only if PDF parsing is required.
- Tests must prove the chosen formats work.

### 6. Ashbel Aluminum-specific lead fields

Status: partially open.

Finding:

- Current parser maps general fields: name, phone, email, city, company, role and notes.
- Lead intelligence supports city, role, source type and segment.

Gap:

Need better normalization for Ashbel Aluminum work:

- Work type.
- Project stage.
- Budget or estimated value.
- Source file.
- Import batch.
- Missing photos.
- Missing plans.
- Missing measurements.
- Proposal readiness fields.
- Decision maker.
- Address.

### 7. Proposal readiness

Status: unverified/open.

Required:

- Locate existing proposal readiness logic or implement it.
- Required states:
  - ready for proposal
  - missing photos
  - missing plans
  - missing measurements
  - missing address
  - missing decision maker
  - missing budget
  - missing project stage
  - proposal follow-up date

### 8. Daily revenue plan proof

Status: unverified/open.

Required:

- Inspect and verify revenue queue/daily plan modules.
- Confirm UI displays top money-making actions.
- Confirm leads imported from files can appear in daily priority flow.

### 9. Outreach safety audit

Status: open.

Finding:

- Approval route can execute outreach task details through `execute_outreach(task)` after approval.
- Draft-modal style approvals appear to log approved draft and emit an event without direct sending.

Required:

- Inspect `engines.outreach_engine` and channel services.
- Confirm real automated customer sending is blocked unless credentials, approval and policy allow it.
- Confirm manual send path is preview/copy/link based.
- Confirm no customer send can occur from import flow.

### 10. UI usability verification

Status: open.

Finding:

- RTL shell and import modal exist.
- Mobile bottom nav exists.

Required:

- Browser test desktop.
- Browser test mobile width.
- Confirm command center is clear.
- Confirm import review is usable.
- Confirm next actions are visible.
- Confirm error/empty/blocked states are helpful.

### 11. HubSpot removal verification

Status: open.

Finding:

- No HubSpot dependency found in inspected active files.

Required:

- Run a repo-wide search for HubSpot terms during local audit.
- Remove or quarantine any active HubSpot references.
- Keep project decision: HubSpot is out of scope entirely.

### 12. Tests to add or verify

Required tests:

- App boot or app factory test.
- Health endpoint test.
- Intake upload dry-run test.
- Intake commit requires approval for full imports.
- Sample data is never committed as real data.
- Real data folder remains Git ignored.
- CSV parse test.
- DOCX parse test if `python-docx` is added.
- Deduplication test.
- Lead score and next action test.
- Proposal readiness test.
- Approval gate blocks outreach.
- Activity/import log test.
- No HubSpot dependency test.

## Completion criteria after final implementation

Development can be called complete only when:

- AshbelOS is the only active system direction.
- HubSpot is absent from active flow.
- The app boots.
- Health endpoint works.
- UI opens.
- Import Center works.
- Real lead file dry run works.
- Preview appears before commit.
- Internal lead commit requires appropriate approval.
- Imported leads appear in UI.
- Leads have score, priority and next action.
- Proposal readiness exists.
- Drafts are generated but not sent.
- Approval gate blocks sensitive actions.
- Daily revenue plan works with imported leads.
- Activity/import logs are created.
- Tests pass.
- A real operator day can run without Excel, HubSpot or chat-only management.

## Next safe action

Run the final implementation planning pass using `docs/NEXT_COMPLETION_RUN.md`, with the specific gaps above as the implementation scope.

Do not deploy and do not import real leads until these gaps are closed and tested.