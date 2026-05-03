# Target System Scope

## Objective

AshbelOS must become the complete daily revenue operating system for Ashbel Aluminum.

The system must not be a static dashboard, a CRM viewer, or a HubSpot wrapper. It must guide the operator from incoming lead to next action, draft, approval, proposal readiness, follow-up, learning and revenue execution.

## Main interface

The main interface is the existing custom AshbelOS UI.

Required primary surfaces:

- Executive Command Center.
- Import Center.
- Leads Intelligence.
- Deals / Opportunities.
- Tasks and Next Actions.
- Message Drafts and Approvals.
- Proposal Readiness.
- Follow-up Management.
- Daily Revenue Plan.
- Weekly Review.
- Activity Log.
- System Health.

## Lead intake

The system must support lead files and discovered lead candidates.

Required behavior:

- Real lead files enter a non-committed raw lead storage location.
- Demo/sample data is stored separately and never treated as real data.
- Dry run is default.
- Preview is required before commit.
- Commit to the internal AshbelOS database requires approval.
- Full import requires approval.
- Supported formats: CSV and DOCX at minimum. XLSX only if safe and simple.
- Normalize name, phone, email, city/settlement, customer type, work type, project stage, source file and import batch.
- Deduplicate by phone, email and normalized name plus city.
- Every lead must receive score, priority, score reason, contact channel, next action and next action date.

## Revenue decision engine

The system must determine:

- Lead quality.
- Hot, warm, medium or low priority.
- Next best action.
- Contact channel recommendation.
- Proposal readiness.
- Follow-up urgency.
- Stuck lead status.
- Missing data status.
- Daily revenue order.

## Outreach and approvals

All customer-facing communication is approval gated.

Required behavior:

- Generate drafts only.
- No email sending without approval and configured credentials.
- No WhatsApp sending without approval and configured credentials.
- No customer contact without explicit approval.
- Every sensitive action follows: Intent, Preview, Approval, Execute, Audit Log.
- Manual send is allowed only after preview and approval.
- Approval states: pending, approved, edited, rejected, expired.

## Proposal readiness

The system must show whether a lead is ready for proposal.

Required fields:

- Ready for proposal.
- Missing photos.
- Missing plans.
- Missing measurements.
- Missing address.
- Missing decision maker.
- Missing budget.
- Missing project stage.
- Proposal follow-up date.
- Proposal metadata.

## Dashboard and command center

Every active screen must answer:

1. What is the current state?
2. What matters now?
3. What is recommended next?
4. What is the primary action?

Dashboard cards must include:

- System status.
- Lead intake status.
- Hot leads.
- Missing phone/email.
- Today's next actions.
- Stuck leads.
- Proposal readiness.
- Proposal follow-ups.
- Message drafts pending approval.
- Approval queue.
- Import errors.
- Source file status.
- Weekly review.
- Next safe action.

## Activity and learning

The system must record:

- Import runs.
- Approval decisions.
- Lead status changes.
- Draft creation.
- Manual send status.
- Follow-up creation.
- Proposal readiness changes.
- Source quality.
- Lead quality by source.
- Conversion placeholders and later real outcomes.

## Integrations

Telegram remains the internal operator channel for commands, approvals and alerts.

GPT Connector and MCP remain interface capabilities, not business source of truth.

Google Drive, n8n, Website form intake, Calendar, Email and WhatsApp Business are future or optional integrations only after the internal AshbelOS flow is proven.

HubSpot is out of scope entirely.