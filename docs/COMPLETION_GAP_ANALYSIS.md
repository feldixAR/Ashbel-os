# Completion Gap Analysis

## Status of this document

This is the initial gap analysis for the alignment run. It must be updated after a focused code audit and before final implementation.

## Immediate strategic gaps

- The current repo contains strong documented capability, but current runtime status must be re-verified.
- The project direction must be locked to the custom AshbelOS system.
- HubSpot must be removed from the active direction and not reintroduced accidentally.
- Real lead intake must be proven in AshbelOS itself, not through external CRM tooling.
- The UI must be verified as usable for a real daily operator workflow.

## Must-have completion gaps

These must be closed before the system can be considered ready for daily work:

1. Confirm current app boot locally.
2. Confirm current health endpoint.
3. Confirm current UI opens.
4. Confirm current command center works.
5. Confirm Import Center or Upload/Import surface exists.
6. Confirm lead file dry run works.
7. Confirm sample data and real lead data are separated.
8. Confirm real lead files are excluded from Git tracking.
9. Confirm lead normalization exists for CSV and DOCX.
10. Confirm duplicate handling exists.
11. Confirm lead scoring and priority exist.
12. Confirm next action and next action date exist.
13. Confirm message drafts are created but not sent.
14. Confirm approval gates block outreach.
15. Confirm proposal readiness exists or implement it.
16. Confirm daily revenue plan works.
17. Confirm activity log records sensitive events.
18. Confirm tests pass after changes.

## UI and UX gaps to verify

- Is the current UI actually clear for Hebrew daily work?
- Are all primary screens RTL-ready?
- Is the mobile layout usable?
- Does every screen answer state, what matters, recommendation and primary action?
- Are empty, loading, error and blocked states useful?
- Does the dashboard lead the operator to the next money-making action?

## Lead and data gaps to verify

- Where should real lead files be placed?
- Are real files ignored by Git?
- Is there a preview screen?
- Is there a commit approval flow?
- Can the operator see import errors?
- Can the operator see missing phone/email?
- Can the operator see hot leads?
- Can the operator see stuck leads?

## Approval and safety gaps to verify

- No real customer outreach without approval.
- No automated WhatsApp send without approval and credentials.
- No automated email send without approval and credentials.
- No full import without approval.
- No destructive actions without approval.
- Every approval produces audit log.

## Cleanup gaps to verify

- Remove or quarantine only what is proven obsolete.
- Do not delete working code without tests or clear proof.
- Identify demo flows.
- Identify old CRM panels.
- Identify inactive sample paths.
- Identify duplicate lead parsing/import paths.
- Identify HubSpot code if present and quarantine or remove from active direction.

## Test gaps to verify

The final run must include or verify tests for:

- App boot.
- Health endpoint.
- UI existence.
- Lead intake dry run.
- Duplicate handling.
- Lead scoring.
- Next action generation.
- Draft generation without sending.
- Approval gate blocking.
- Proposal readiness.
- Daily revenue queue.
- Activity log.
- Sample vs real data separation.
- No HubSpot dependency.

## Runtime verification gaps

Do not rely only on historical docs. Verify now:

- Local boot.
- Local test command.
- Production health only after local confidence.
- UI rendering.
- API routes.
- Database migrations.

## External integrations

These are not blockers for internal daily work:

- Google Drive.
- n8n.
- Website forms.
- Calendar.
- Email sending.
- WhatsApp Business.

They may be added after the internal system is proven.

## Definition of done

The system is development-complete only when:

- AshbelOS is the main system.
- HubSpot is absent from active direction.
- The UI opens and supports daily operation.
- Existing leads can be imported internally after preview and approval.
- Leads appear with score, priority and next action.
- Drafts and approvals work.
- Proposal readiness works.
- Daily revenue plan works.
- Activity log works.
- Tests pass.
- A real operator day can be executed without Excel, HubSpot or chat-only management.

## Next action

Run the focused audit and fill concrete path-level findings in `docs/SYSTEM_AUDIT_MAP.md`. Then freeze the final implementation plan in `docs/NEXT_COMPLETION_RUN.md`.