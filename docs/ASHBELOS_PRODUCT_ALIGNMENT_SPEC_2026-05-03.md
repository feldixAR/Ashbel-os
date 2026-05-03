# AshbelOS Product Alignment Spec 2026-05-03

## Purpose

This document defines the product alignment plan for AshbelOS as Ashbel Aluminum's daily revenue operating system. It is not a generic CRM, not HubSpot, and not a technical dashboard. The system must guide the operator through revenue work: which lead matters, why it matters, what to do now, what requires approval, and what must not happen without approval.

## Product principle

Every screen must answer five questions:

1. What is important now?
2. Why is it important?
3. What should I do next?
4. What is missing or blocking progress?
5. What requires approval before execution?

If a screen shows data without answering these questions, it is incomplete.

## Core operating model

The correct flow is:

Intent -> Preview -> Business review -> Approval -> Commit -> Daily work queue -> Draft -> Approval -> Manual or approved execution -> Audit log

Sensitive actions remain blocked unless explicitly approved.

## Primary product areas

1. Executive Revenue Dashboard
2. Business Import Review
3. Leads Intelligence
4. Daily Revenue Queue
5. Approval Center
6. Draft Studio
7. Activity and Audit Log
8. Proposal Readiness
9. System QA Console
10. Frontend Autonomous QA

---

# 1. Business Import Review

## Current gap

The current import preview shows groups and numeric scores. That is not enough for business use. The operator needs to understand whether a lead requested aluminum, what construction stage the project is in, how urgent it is, and what the next action should be.

## Required preview record fields

Each imported record must include:

- owner_name
- contact_name
- phone
- email
- city_or_settlement
- construction_stage
- aluminum_intent
- aluminum_intent_label
- work_type_detected
- timing_window
- urgency_level
- score
- score_breakdown
- business_reason
- recommended_action
- proposal_readiness
- missing_fields
- import_recommendation

## Aluminum intent classification

| Classification | Meaning | Product behavior |
|---|---|---|
| explicit_aluminum | The text explicitly includes aluminum or a clear aluminum product | Strong intent |
| all_fields | The lead asked for all fields/all suppliers/all areas | Potential intent, requires clarification |
| adjacent_aluminum | Mentions pergolas, gates, fences, railings, Belgian windows or similar | Relevant secondary intent |
| no_aluminum | No aluminum or adjacent field appears | Low relevance unless another reason exists |
| unknown | Parser cannot determine | Manual review |

## Construction stage classification

| Stage | Business meaning | Timing |
|---|---|---|
| planning | Early planning | Follow up in several months |
| permits | Early administrative stage | Long follow-up |
| foundations | Early construction | Relationship opening, future follow-up |
| early_skeleton | Relevant but early | Follow-up in 30-60 days |
| mid_skeleton | Strong timing | Contact this week |
| late_skeleton | Very strong timing | Contact now |
| plaster | Critical timing | Contact immediately |
| finishing | Late, urgent or missed window | Immediate clarification |
| unknown | Not detected | Manual review |

## Lead heat logic

A lead is not hot because of a high numeric score alone. It is hot only when business context supports urgency.

### Hot now

- Explicit aluminum plus plaster, late skeleton or mid skeleton
- All-fields request plus plaster or late skeleton
- Adjacent aluminum product plus strong contact details and advanced stage

### Warm

- Explicit aluminum plus early skeleton or foundations
- All-fields request plus mid skeleton
- Adjacent aluminum product plus early or mid skeleton

### Follow-up

- Explicit aluminum but planning or foundations
- All-fields request but early stage
- Good lead but timing is future

### Manual review

- Missing contact method
- Unclear stage
- Unclear intent
- Conflicting data

### Skip or archive

- No aluminum intent
- No adjacent field
- No contact method
- Irrelevant sector

## Score model

The score must be visible as a breakdown, not only as one number.

Suggested scoring categories:

| Category | Max score | Examples |
|---|---:|---|
| Aluminum intent | 35 | explicit aluminum: 35, all fields: 18, adjacent: 14, none: 0 |
| Construction timing | 30 | plaster: 30, late skeleton: 27, mid skeleton: 23, early skeleton: 16, foundations: 8, planning: 5 |
| Contactability | 15 | phone and email: 15, phone only: 12, email only: 8, none: 0 |
| Work scope | 10 | full aluminum package: 10, windows/doors: 8, pergola/fence/railing: 5 |
| Geography | 5 | target service area: 5, acceptable: 3, far: 0 |
| Proposal readiness | 5 | enough data for next commercial step: 5 |

## Preview card display

Each imported lead card should show:

- Name and location
- Contact method
- Stage badge
- Aluminum intent badge
- Timing window badge
- Score and score breakdown
- Business reason
- Recommended action
- Missing proposal data
- Row action: Import, Review, Skip

## Preview group labels

Replace generic groups with business groups:

1. Hot now
2. Clarify aluminum
3. Follow-up future
4. Missing information
5. Duplicate or already exists
6. Not relevant

## Button language

Replace risky/generic wording:

| Current | Replace with |
|---|---|
| אשר הכל הרלוונטי | אשר לידים מומלצים בלבד |
| ייבא אושרו | העבר לאישור ייבוא |
| ייבא | סמן לייבוא |
| בדוק | דורש בדיקה |
| דלג | דלג |

## Import approval copy

Before commit, the UI must state:

- This does not send messages.
- This only writes selected leads into AshbelOS.
- This action requires approval.
- Number of records selected.
- Number of hot leads.
- Number of missing contact details.
- Number of duplicates skipped.

---

# 2. Daily Revenue Dashboard

## Purpose

The dashboard must not be a passive list. It must be the daily control center.

## Required dashboard zones

1. Main next action: the single most important action now
2. Hot now: leads requiring contact today
3. Clarify aluminum: leads that may need aluminum but did not explicitly say so
4. Follow-up future: good leads too early for proposal
5. Stuck leads: missing phone, plans, measurements, address or decision maker
6. Waiting for approval: imports, drafts, outreach actions
7. Drafts ready: messages prepared but not sent
8. Revenue potential: rough value by timing window
9. System safety: no automatic sending, approval required

## Dashboard rule

Every displayed lead must show:

- why now
- next action
- blocker if any
- approval state if relevant

---

# 3. Approval Center

## Approval types

The system must separate approval types:

1. Import commit approval
2. Draft approval
3. Outreach execution approval
4. System change approval

## Approval card must show

- Approval type
- What will happen if approved
- What will not happen
- Risk level in Hebrew
- Affected lead or file
- Preview of affected data
- Created time
- Approve / Reject / Return for edit

## Import approval must show

- Source file
- Import run ID
- Number of records
- Hot leads
- Missing information
- Duplicates
- Confirmation that no outreach will be sent

## Outreach approval must show

- Channel
- Recipient
- Message body
- Whether execution is manual or automated
- Confirmation that credentials and policy allow execution

---

# 4. Proposal Readiness

## Required fields

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

## UI behavior

A lead must never simply say “not ready”. It must say what is missing and what to request.

Examples:

- Missing plans: ask customer to send architectural plans.
- Missing measurements: ask for opening dimensions.
- Missing photos: ask for site photos.
- Missing budget: do not ask directly first; infer from project scope when possible.

---

# 5. Frontend Autonomous QA

## Goal

Build a browser-facing QA capability that verifies the product as a user experiences it, not only as an API test.

## Required QA layers

1. API QA: health, DB, auth, routes
2. Business QA: scoring, aluminum intent, construction stage, next action
3. Frontend QA: screens, modals, buttons, error states, mobile RTL
4. Visual QA: screenshots and spec comparison

## Required browser walkthroughs

1. Load dashboard
2. Login with API key in test mode
3. Open System QA Console
4. Open Import Center
5. Upload synthetic CSV
6. Confirm preview appears
7. Try uploading the same file again
8. Confirm input reset works
9. Confirm explained business scoring appears
10. Confirm selected import requires approval
11. Open approval center
12. Confirm approval explains what will happen
13. Approve only synthetic import
14. Complete commit
15. Confirm lead appears in Leads
16. Confirm Daily Revenue Queue includes hot lead
17. Confirm Proposal Readiness appears
18. Confirm Draft is generated but not sent
19. Confirm WhatsApp/Email are not sent
20. Run mobile viewport check
21. Save screenshots
22. Produce pass/fail/spec-gap report

## QA report must include

- Timestamp
- Commit hash
- Environment
- Viewport
- Screens tested
- Screenshots
- Passed checks
- Failed checks
- Spec mismatches
- Accessibility notes
- RTL notes
- Mobile notes
- Risk level
- Exact next action

## QA safety rules

- Read-only by default
- Synthetic data only
- No real customer data
- No outreach
- No external sending
- Any commit requires explicit operator approval

---

# 6. UI cleanup principles

## Visual hierarchy

The UI must emphasize action priority:

1. Action now
2. Why now
3. Blocking issues
4. Approval state
5. Secondary data

## Language rules

- Hebrew business language, not developer language
- No generic CRM language when business-specific language is possible
- No ambiguous action buttons
- No hidden consequences
- No unexplained score

## Mobile rules

- All primary actions must be usable on mobile
- Import review cards must stack vertically
- Buttons must be large enough to tap
- No horizontal overflow for critical data
- RTL must remain correct in every modal

---

# 7. Definition of Done

The system is product-aligned only when:

1. CSV import preview works.
2. DOCX Bonim Israel import preview works.
3. Preview explains business meaning, not only score.
4. Aluminum intent is classified.
5. Construction stage is classified.
6. Timing window is shown.
7. Recommended next action is shown.
8. Import approval is clear.
9. Commit does not send outreach.
10. Imported lead appears in Leads.
11. Hot lead appears in Daily Revenue Queue.
12. Proposal readiness is visible.
13. Drafts require approval.
14. QA Console loads from browser.
15. Frontend QA can capture screenshots.
16. Mobile UI is usable.
17. No HubSpot references in active product flow.
18. No demo or placeholder text remains in production UI.
19. No real lead files are committed.
20. No customer outreach is sent without explicit approval.

---

# 8. Current known open gaps

1. Connect Bonim parser helper to active document_intelligence parse flow.
2. Upgrade import preview to Business Import Review.
3. Replace numeric-only score display with business scoring explanation.
4. Add construction-stage timing logic.
5. Add aluminum-intent classification to records and UI.
6. Rename import action buttons.
7. Reset file input after upload attempt.
8. Strengthen approval copy.
9. Add frontend browser QA automation.
10. Add screenshot-based QA reporting.
11. Perform mobile visual review.
12. Remove or rewrite generic CRM/demo language.

## Next planning step

Before implementation, lock the Business Import Review data contract and the Frontend Autonomous QA contract. Then implementation should be minimal and sequential: parser connection, scoring explanation, preview UI, approval copy, QA automation, visual cleanup.
