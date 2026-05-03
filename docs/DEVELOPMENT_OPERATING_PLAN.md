# Development Operating Plan

## Purpose

This document controls how AshbelOS development continues from here. It prevents drift between chat instructions, old repos, HubSpot direction, partial prompts and unverified assumptions.

## Required process

All work must follow this order:

1. Context Lock.
2. Audit.
3. Plan Freeze.
4. One Completion Run.
5. Verify.
6. Lead intake dry run.
7. Approved internal commit.
8. Controlled daily operation.
9. External automations only after the internal system works.

## Phase 1: Context Lock

- Confirm primary repo is `feldixAR/Ashbel-os`.
- Confirm HubSpot is out of scope.
- Confirm AshbelOS custom UI is the main interface.
- Confirm all future prompts read project control docs first.
- Confirm no implementation starts from chat memory alone.

## Phase 2: Audit

- Inspect only relevant files first.
- Verify app entrypoint, run command, UI entrypoint, API routes, models, agents, skills, tests and storage.
- Distinguish code-verified facts from documented claims.
- Do not refactor during audit.
- Do not import leads during audit.
- Do not contact customers.

## Phase 3: Plan Freeze

- Convert audit findings into exact implementation scope.
- Define what will be built.
- Define what will not be built.
- Define what stays blocked.
- Define validation commands.
- Define final report format.
- Do not expand scope after freeze unless a true blocker is found.

## Phase 4: One Completion Run

The completion run may implement only the approved scope. It should be broad enough to finish the system but not broad enough to create a parallel architecture.

Allowed:

- Extend existing modules.
- Complete missing UI surfaces.
- Complete lead intake.
- Complete scoring, next actions, drafts, approvals, proposal readiness and activity logs.
- Add tests.
- Clean or quarantine obsolete code only with proof.

Not allowed:

- New CRM.
- Parallel system.
- HubSpot-first direction.
- Deleting working code without proof.
- Real customer outreach.
- Real full import without approval.
- Deployment without verification.

## Phase 5: Verify

Verification must prove:

- App boots.
- Health endpoint works.
- UI opens.
- Import Center exists.
- Lead dry run works.
- Sample and real data are separated.
- Scoring works.
- Next action works.
- Drafts are generated but not sent.
- Approval gate blocks sensitive actions.
- Proposal readiness works.
- Daily revenue plan works.
- Activity log records.
- Tests pass.

## Phase 6: Existing lead intake

- Place real lead files outside Git-tracked sample data.
- Run dry run.
- Review preview.
- Check duplicates and missing fields.
- Approve internal commit only after review.
- Confirm leads appear in UI.
- Do not send messages.

## Phase 7: Daily operation

First working day must prove:

- Command Center shows top leads.
- Daily Revenue Plan shows what to do today.
- Drafts are reviewable.
- Approvals are controlled.
- Follow-ups are created.
- Activity log records actions.

## Phase 8: External automations

Only after the internal system works:

- Google Drive can be connected for lead files.
- n8n can be connected for scheduled automations.
- Website forms can feed intake.
- Calendar can support site visits.
- Email and WhatsApp require explicit approval and credentials.

## Prompt rule

Every future prompt must begin with:

Read the project control docs first. If the requested work conflicts with them, stop and report the conflict.

## Completion rule

Development is not complete until the system can run a real operator day using real leads inside AshbelOS without depending on HubSpot.