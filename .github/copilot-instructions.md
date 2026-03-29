# AshbelOS Copilot Instructions

## Stack
- Backend: Flask + Gunicorn (Python 3.11), Railway, PostgreSQL
- Phase 11 scoring: engines/phase11_engine.py (source of truth)

## Lead statuses (DB values, Hebrew)
- חדש, ניסיון קשר, מתעניין, סגור_זכה, סגור_הפסיד

## Phase 11 business states (scoring layer only)
- NEW_LEAD, QUOTE_SENT, AWAITING_MEASUREMENTS, AWAITING_APPROVAL, AWAITING_DEPOSIT, BLOCKED_CRITICAL

## Rules
- Token-efficient, one-pass execution
- Do not refactor stable FSM logic
- Run pytest before commit
