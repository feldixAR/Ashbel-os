# Project Control Documents

Future agents must read these documents before planning or implementing AshbelOS changes.

Required order:

1. `docs/CURRENT_PROJECT_STATE.md`
2. `docs/REPO_DECISION.md`
3. `docs/TARGET_SYSTEM_SCOPE.md`
4. `docs/DEVELOPMENT_OPERATING_PLAN.md`
5. `docs/SYSTEM_AUDIT_MAP.md`
6. `docs/COMPLETION_GAP_ANALYSIS.md`
7. `docs/NEXT_COMPLETION_RUN.md`
8. `CLAUDE.md`
9. `docs/ashbelos-governance.md`
10. `docs/PRODUCT_OPERATING_MODEL.md`
11. `docs/UI_UX_MOBILE_RULES.md`
12. `docs/DEPLOY_AND_VERIFICATION_DISCIPLINE.md`

## Locked instruction

If a requested change conflicts with these control documents, stop and report the conflict before editing code.

## Current project direction

- `feldixAR/Ashbel-os` is the primary system.
- AshbelOS custom UI is the primary interface.
- HubSpot is out of scope entirely.
- No new CRM.
- No parallel system.
- No customer outreach without approval.
- No real import without preview and approval.
- Dry run remains default for sensitive actions.

## Next step

Run a focused audit that fills `docs/SYSTEM_AUDIT_MAP.md` with concrete path-level findings and updates `docs/COMPLETION_GAP_ANALYSIS.md` before final implementation.