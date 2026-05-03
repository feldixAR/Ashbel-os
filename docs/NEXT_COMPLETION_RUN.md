# Next Completion Run

## Status

Approved to proceed by operator on 2026-05-03.

This document is now the frozen scope for the final implementation run. The implementation run must follow this document and the project control docs.

## Objective

Complete AshbelOS as the primary working system for Ashbel Aluminum, with internal lead intake, dashboard, scoring, next actions, drafts, approvals, proposal readiness, activity log and daily revenue workflow.

HubSpot is out of scope.

## Required pre-read

Every final implementation prompt must read:

- `docs/PROJECT_CONTROL_DOCUMENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/REPO_DECISION.md`
- `docs/TARGET_SYSTEM_SCOPE.md`
- `docs/DEVELOPMENT_OPERATING_PLAN.md`
- `docs/SYSTEM_AUDIT_MAP.md`
- `docs/COMPLETION_GAP_ANALYSIS.md`
- `docs/NEXT_COMPLETION_RUN.md`
- `CLAUDE.md`
- `docs/ashbelos-governance.md`
- `docs/PRODUCT_OPERATING_MODEL.md`
- `docs/UI_UX_MOBILE_RULES.md`
- `docs/DEPLOY_AND_VERIFICATION_DISCIPLINE.md`

If requested work conflicts with these documents, stop and report the conflict.

## Final implementation command for Codex / Claude Code

```text
You are working in repo feldixAR/Ashbel-os on branch control/alignment-run-2026-05-03.

Read the project control docs first. If the requested work conflicts with them, stop and report the conflict.

Required pre-read:
- docs/PROJECT_CONTROL_DOCUMENTS.md
- docs/CURRENT_PROJECT_STATE.md
- docs/REPO_DECISION.md
- docs/TARGET_SYSTEM_SCOPE.md
- docs/DEVELOPMENT_OPERATING_PLAN.md
- docs/SYSTEM_AUDIT_MAP.md
- docs/COMPLETION_GAP_ANALYSIS.md
- docs/NEXT_COMPLETION_RUN.md
- CLAUDE.md
- docs/ashbelos-governance.md
- docs/PRODUCT_OPERATING_MODEL.md
- docs/UI_UX_MOBILE_RULES.md
- docs/DEPLOY_AND_VERIFICATION_DISCIPLINE.md

Goal:
Complete AshbelOS as the primary daily working system for Ashbel Aluminum. Do not build a new CRM. Do not create a parallel system. Do not use or reintroduce HubSpot. HubSpot is out of scope entirely.

Binding decisions:
- Primary repo: feldixAR/Ashbel-os.
- Primary UI: existing AshbelOS custom operator console.
- Business context: Ashbel Aluminum, Hebrew, RTL, ILS.
- HubSpot: out of scope entirely.
- Real lead files must not be committed to GitHub.
- Dry run and preview are mandatory before import commit.
- Full import or large commit requires explicit approval.
- All customer outreach requires approval.
- No automated customer sending unless explicitly approved, credentialed and policy-compliant.
- Do not deploy in this run.
- Do not contact customers.
- Do not send email or WhatsApp messages.

Implementation scope:

1. Runtime and safety audit before edits
- Confirm app entrypoint and local run command.
- Confirm test command.
- Confirm existing route registration.
- Search for HubSpot references and remove/quarantine any active direction.
- Inspect engines.outreach_engine and services/channels to verify no customer send can bypass approval.
- Inspect storage models for Lead, Task, Approval, Activity, ImportRun and proposal readiness equivalents.
- Inspect revenue queue and daily plan modules.
- Inspect console UI and upload modal flow.

2. Lead data folder discipline
- Add clear local folder convention if missing:
  - data/raw_leads
  - data/samples
  - data/processed
  - data/import_reports
- Ensure real lead files remain ignored by Git.
- Add safe placeholder README or .gitkeep only if appropriate and not leaking data.
- Ensure sample data cannot be committed as real import by default.

3. Document import dependencies
- Add required dependencies for supported formats.
- At minimum add python-docx if DOCX lead files are expected.
- Add openpyxl only if XLSX is supported in production.
- Add pdfplumber only if PDF parsing is supported in production.
- Add tests for every supported format.

4. Intake hardening
- Keep /api/intake/upload as dry-run preview.
- Add or complete formal import approval for commit when needed.
- Small row-level approval in UI can remain, but full file/import commit must be policy-safe.
- Add approval_id requirement or approval creation flow for commit when appropriate.
- Add import size threshold rules if needed.
- Ensure preview includes source_file, raw_count, approved_count, skipped, duplicates, missing phone/email, hot leads and import warnings.
- Ensure commit writes only approved records.
- Ensure commit never sends outreach.

5. ImportRun and activity logging
- Add or complete ImportRun model/repository or equivalent persistent import report.
- Record source file, format, raw count, approved count, created count, skipped count, duplicates, errors, operator, timestamp and lead IDs.
- Write activity/audit log for import commit.
- Produce readable import report for dashboard/UI.

6. Ashbel Aluminum lead normalization
- Extend parsing/normalization to capture where possible:
  - work_type
  - project_stage
  - estimated_value or budget when present
  - source_file
  - import_batch
  - address
  - decision_maker
  - notes
  - missing_photos
  - missing_plans
  - missing_measurements
- Preserve backward compatibility with existing lead model. If DB changes are needed, add safe migrations consistent with existing migration style.

7. Lead scoring and next actions
- Strengthen scoring for Ashbel Aluminum:
  - project stage
  - work type
  - location/settlement/city
  - contact completeness
  - urgency
  - proposal readiness
  - estimated value when present
- Every lead must get score, priority, score reason, next action and next action date or a clear blocked reason.

8. Proposal readiness
- Implement or complete proposal readiness logic.
- Required fields/states:
  - ready_for_proposal
  - missing_photos
  - missing_plans
  - missing_measurements
  - missing_address
  - missing_decision_maker
  - missing_budget
  - missing_project_stage
  - proposal_followup_date
  - proposal_metadata
- Surface proposal readiness in API and UI.

9. Daily revenue plan
- Ensure imported leads can appear in daily revenue queue/plan.
- Prioritize actions by expected revenue, urgency, score and readiness.
- UI must show top actions for today and why they matter.

10. UI completion
- Keep the existing custom UI.
- Improve the existing Operating Console, do not replace it.
- Make Import Center clear and usable.
- Show import status, errors, hot leads, missing phone/email, duplicates and next safe action.
- Show proposal readiness.
- Show message drafts pending approval.
- Show today's next actions and stuck leads.
- Ensure Hebrew RTL and mobile usability.
- Add clear empty, loading, error and blocked states where missing.

11. Outreach safety
- Drafts only unless approval exists.
- Manual send must be preview/copy/deep-link based.
- Automated sends remain blocked unless explicitly configured and approved.
- Add tests proving imports do not send outreach and drafts require approval.

12. Tests
Add or update tests for:
- app factory / boot
- health endpoint
- intake upload dry run
- CSV parse
- DOCX parse if supported
- XLSX parse if supported
- sample data not treated as real data
- real data path ignored
- duplicate detection
- lead scoring and next action
- import approval requirement
- ImportRun/import report logging
- proposal readiness
- daily revenue queue includes imported leads
- drafts generated but not sent
- approval blocks outreach
- no HubSpot dependency in active flow
- UI files/routes exist

13. Validation
Run local validation only:
- install dependencies if needed
- run relevant tests
- run full test suite if feasible
- verify app boot if feasible
- do not deploy
- do not import real leads
- do not contact customers
- do not send messages

Final report only:
1. files created
2. files changed
3. files quarantined or removed
4. runtime/app facts verified
5. HubSpot removal status
6. intake/import status
7. approval hardening status
8. ImportRun/activity log status
9. proposal readiness status
10. daily revenue plan status
11. UI status
12. outreach safety status
13. tests run and results
14. blockers
15. exact next safe command
```

## Final implementation checklist

- [ ] Runtime and safety audit before edits.
- [ ] HubSpot references searched and removed/quarantined from active flow.
- [ ] Real lead data folder discipline completed.
- [ ] Required document import dependencies added.
- [ ] Intake preview preserved.
- [ ] Import commit approval hardened.
- [ ] ImportRun or equivalent import report added.
- [ ] Activity log records imports.
- [ ] Ashbel Aluminum fields normalized.
- [ ] Lead scoring strengthened.
- [ ] Next actions completed.
- [ ] Proposal readiness completed.
- [ ] Daily revenue plan supports imported leads.
- [ ] UI Import Center completed.
- [ ] Dashboard cards completed.
- [ ] Outreach safety verified.
- [ ] Tests added or updated.
- [ ] Local validation run.
- [ ] No deployment.
- [ ] No real outreach.

## Cleanup rules

- Do not build a new CRM.
- Do not create a parallel app.
- Do not delete working code without proof.
- Do not reintroduce HubSpot.
- Do not commit real lead files.
- Do not commit secrets.
- Do not send messages.
- Do not contact customers.
- Do not deploy during implementation unless explicitly approved later.

## Final report format

Return only:

1. files created
2. files changed
3. files quarantined or removed
4. audit facts verified
5. implementation completed
6. lead intake status
7. dashboard status
8. approval status
9. proposal readiness status
10. activity log status
11. tests run and result
12. blockers
13. exact next safe command

## Next safe command

Run the final implementation command above in Codex or Claude Code inside the repo working tree on branch `control/alignment-run-2026-05-03`.