# System Audit Map

## Status of this document

This is the initial audit map created during the alignment run. It separates code-verified facts from items still requiring a focused local audit.

## Code and docs verified during alignment

- Repo: `feldixAR/Ashbel-os`.
- Default branch: `master`.
- README identifies the product as AshbelOS for Ashbel Aluminum.
- README states stack: Python 3.11, Flask, Gunicorn, PostgreSQL and Railway.
- README states production URL: `https://ashbel-os-production.up.railway.app`.
- CLAUDE.md exists and contains architecture, batch inventory and production closeout history.
- Governance doc exists.
- Product operating model exists.

## Architecture from repo docs

Documented flow:

1. Dashboard UI / WhatsApp.
2. `api/routes/*.py` as Flask Blueprints.
3. `orchestration/orchestrator.py` for intent to task mapping.
4. `orchestration/task_manager.py` for task lifecycle.
5. `services/execution/executor.py` for action dispatch.
6. `engines/*.py` and `agents/**` for domain logic.
7. `services/storage/` for PostgreSQL through SQLAlchemy.

## Source-of-truth docs to inspect in final audit

- `README.md`
- `CLAUDE.md`
- `docs/ashbelos-governance.md`
- `docs/ashbelos-token-efficiency-policy.md`
- `docs/PRODUCT_OPERATING_MODEL.md`
- `docs/AGENTS_SKILLS_ORCHESTRATION.md`
- `docs/UI_UX_MOBILE_RULES.md`
- `docs/DEPLOY_AND_VERIFICATION_DISCIPLINE.md`
- `docs/API.md`
- `docs/TELEGRAM.md`
- `docs/FALLBACK.md`
- `docs/INTEGRATIONS.md`

## Areas to map in the next focused audit

### App and runtime

- App entrypoint.
- Gunicorn entrypoint.
- Local run command.
- Test command.
- Environment variables.
- Database startup and migrations.

### API routes

Map routes related to:

- Health.
- Command.
- Leads.
- Lead operations.
- Approvals.
- Revenue.
- Dashboard / Home.
- System.
- Learning.
- Telegram.
- GPT connector.
- MCP.
- Channels.
- Marketing.
- Calendar.
- Tasks.

### UI

Map:

- `ui/index.html`.
- Shell controller.
- Home / Command Center.
- Leads panel.
- Console panel.
- Approvals panel.
- Communications panel.
- Import or Upload panel.
- Draft modal.
- Mobile CSS.
- Empty, loading, error and blocked states.

### Lead and intake modules

Map:

- Lead model.
- Contact / client model.
- Task model.
- Approval model.
- Activity model.
- Import run model, if present.
- Intake normalizer.
- Document intelligence parser.
- Lead acquisition engine.
- Lead scoring logic.
- Deduplication logic.

### Agents and skills

Map:

- Agent registry.
- Lead acquisition agent.
- Follow-up agent.
- Reporting agent.
- Channel strategy agent.
- Marketing strategy agent.
- SEO agent.
- Learning skills.
- Lead intelligence skills.
- Outreach intelligence skills.
- Document intelligence skills.

### Revenue and daily operation

Map:

- Daily revenue queue.
- Revenue scoring.
- Next best action.
- Proposal readiness.
- Follow-up queue.
- Weekly review.
- Learning snapshot.

### Integrations

Map:

- Telegram operator flow.
- GPT connector.
- MCP endpoint.
- Manual send readiness.
- Email readiness.
- WhatsApp readiness.
- Google Drive readiness, if any.
- n8n readiness, if any.

### Tests

Map tests for:

- Bootstrapping.
- Health.
- Product fit.
- Lead acquisition.
- Approvals.
- Revenue queue.
- Learning feedback.
- Scheduler.
- Cross-surface truth.
- UI behavior.

## Suspected obsolete or risk areas to verify

- Demo profile or demo real estate scaffolding.
- Old generic CRM views that do not support Ashbel Aluminum daily work.
- Channel execution code that could bypass approval gates.
- Any HubSpot-related code, if present.
- Sample data paths that could be confused with real data.
- Old UI panels that are no longer in active navigation.
- Duplicate import or lead parsing paths.

## Required audit output before implementation

The next audit must update this file with concrete paths and current status:

- Exists and working.
- Exists but incomplete.
- Exists but obsolete.
- Missing.
- Requires runtime verification.

No final implementation should start until this map is filled with concrete repo facts.