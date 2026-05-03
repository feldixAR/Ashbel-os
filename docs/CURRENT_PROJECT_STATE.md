# Current Project State

## Locked status

- Primary repo: `feldixAR/Ashbel-os`.
- Primary branch: `master`.
- Primary UI: the existing custom AshbelOS operator console.
- Business profile: `ashbel`, Ashbel Aluminum, Hebrew, ILS.
- HubSpot status: removed from the project direction. Do not use as UI, sync, export, backup, or fallback unless a future explicit decision reverses this.
- Secondary repo: `feldixAR/Ashbel_Aluminum_Revenue_OS` is reference material only for operating discipline. It is not the active product.
- Empty repo: `feldixAR/Repository-name-ashbal-os` is irrelevant unless proven otherwise.

## Current stack from repo docs

- Python 3.11.
- Flask plus Gunicorn.
- PostgreSQL through Railway.
- Railway deployment from `master`.
- Static custom UI under `ui/`.
- API routes under `api/routes/`.
- Business logic through orchestrator, task manager, executor, engines, agents, skills, storage and scheduler.

## Current production status from repo docs

Repository docs state that production was verified as v10.0, with 21 of 21 API endpoints passing on Railway production.

This is a documented status, not a fresh runtime verification from this alignment run. The next audit must verify current runtime and local status before claiming the system is ready now.

## Current system capabilities stated in repo docs

The repo documentation states that AshbelOS includes:

- CRM core.
- Assistant and draft flow.
- Agent Factory.
- Revenue Engine.
- Scheduler.
- Goal and Growth Engine.
- Research and Asset Engine.
- Outreach and Execution Engine.
- Revenue Learning Engine.
- Mobile quick actions.
- Daily Revenue Queue.
- Lead Acquisition OS.
- LeadAcquisitionAgent.
- Approval execute flow.
- Telegram operator flow.
- GPT Connector.
- MCP endpoint.
- Dashboard UI.
- Learning snapshot.
- Self evolution.
- Manual send readiness.
- WhatsApp draft readiness.
- Email readiness.
- Marketing Engine.
- SEO Agent.
- Command first UI.

## What is verified in this alignment layer

- The primary repo exists and is non-empty.
- The README identifies AshbelOS as the autonomous business operating system for Ashbel Aluminum.
- The repo docs describe the custom UI as the daily operating surface.
- The governance docs define AshbelOS as the independent business core.
- The product operating model defines the system as a primary operating console, not a dashboard or CRM viewer.

## What is not yet verified in this alignment layer

- Current local boot.
- Current production runtime.
- Current UI rendering.
- Current database migrations.
- Current test count.
- Current lead intake behavior with real files.
- Current import center completeness.
- Current state of demo or obsolete code.
- Current readiness to ingest real leads.

## Current blockers and risks

- Real lead files must not be committed to GitHub.
- No real import until dry run and approval are proven.
- No customer outreach without explicit approval.
- External automation can be added later only after the internal system works.
- HubSpot must not re-enter the direction unless explicitly approved later.

## Next required action

Run a focused system audit against the repo and update `docs/SYSTEM_AUDIT_MAP.md` and `docs/COMPLETION_GAP_ANALYSIS.md` with code-verified facts before final implementation.