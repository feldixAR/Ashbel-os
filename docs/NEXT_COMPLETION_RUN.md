# Next Completion Run

## Status

Prepared during the alignment run. Do not execute final implementation until the focused audit updates `docs/SYSTEM_AUDIT_MAP.md` and `docs/COMPLETION_GAP_ANALYSIS.md` with concrete repo facts.

## Objective

Complete AshbelOS as the primary working system for Ashbel Aluminum, with internal lead intake, dashboard, scoring, next actions, drafts, approvals, proposal readiness, activity log and daily revenue workflow.

HubSpot is out of scope.

## Required pre-read

Every final implementation prompt must read:

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

## Audit checklist before implementation

- Confirm app entrypoint.
- Confirm local run command.
- Confirm test command.
- Confirm UI entrypoint.
- Confirm current API routes.
- Confirm lead models.
- Confirm intake modules.
- Confirm approval modules.
- Confirm revenue queue modules.
- Confirm proposal readiness state.
- Confirm activity log state.
- Confirm import/upload UI state.
- Confirm sample and real data paths.
- Confirm Git ignores real lead files and secrets.
- Confirm no HubSpot dependency exists in active flow.

## Implementation checklist

Implement only after audit findings are concrete.

- Complete Import Center.
- Complete real lead file dry run.
- Complete preview before commit.
- Complete approved internal commit.
- Complete sample/real data separation.
- Complete deduplication.
- Complete lead scoring.
- Complete priority and score reason.
- Complete contact channel recommendation.
- Complete next action and next action date.
- Complete daily revenue plan.
- Complete message draft generation.
- Complete approval queue.
- Complete proposal readiness.
- Complete follow-up queue.
- Complete activity log.
- Complete dashboard cards.
- Complete UI Hebrew/RTL/mobile usability.
- Complete system health and operator next safe action.
- Quarantine obsolete/demo code only when proven safe.
- Update docs.
- Add or update tests.

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

## Validation checklist

- App boots.
- Health endpoint works.
- UI opens.
- Import Center exists.
- Lead dry run works.
- Preview is generated.
- Commit requires approval.
- Sample data and real data are separated.
- Duplicates are detected.
- Score and priority are generated.
- Next actions are generated.
- Drafts are generated but not sent.
- Approval gate blocks outreach.
- Proposal readiness works.
- Daily revenue plan works.
- Activity log records.
- Tests pass.
- HubSpot is not required and not used.

## Final report format for Codex

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

## Exact next safe command placeholder

The next safe command is not final implementation yet.

Next required action:

Run a focused audit that fills `docs/SYSTEM_AUDIT_MAP.md` with concrete paths and updates `docs/COMPLETION_GAP_ANALYSIS.md` before implementation.