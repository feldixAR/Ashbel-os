-- =============================================================================
-- Migration: 001_initial
-- Description: Full schema for AshbalOS — all tables
-- Compatible: PostgreSQL (production) and SQLite (development)
-- Note: JSON columns use TEXT in SQLite; SQLAlchemy handles serialization
-- =============================================================================

-- ── agents ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id               VARCHAR(36)  PRIMARY KEY,
    name             VARCHAR(120) NOT NULL,
    role             VARCHAR(120) NOT NULL,
    department       VARCHAR(80)  NOT NULL,
    active_version   INTEGER      NOT NULL DEFAULT 1,
    model_preference VARCHAR(60)  NOT NULL DEFAULT 'claude_haiku',
    risk_tolerance   INTEGER      NOT NULL DEFAULT 2,
    capabilities     TEXT         NOT NULL DEFAULT '[]',   -- JSON array
    active           BOOLEAN      NOT NULL DEFAULT TRUE,
    tasks_done       INTEGER      NOT NULL DEFAULT 0,
    last_active_at   VARCHAR(40),
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agents_department ON agents(department);
CREATE INDEX IF NOT EXISTS idx_agents_active     ON agents(active);

-- ── agent_versions ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_versions (
    id               VARCHAR(36)  PRIMARY KEY,
    agent_id         VARCHAR(36)  NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version          INTEGER      NOT NULL,
    system_prompt    TEXT         NOT NULL,
    model_preference VARCHAR(60)  NOT NULL,
    is_active        BOOLEAN      NOT NULL DEFAULT FALSE,
    tasks_executed   INTEGER      NOT NULL DEFAULT 0,
    success_rate     FLOAT,
    avg_quality_score FLOAT,
    avg_latency_ms   FLOAT,
    avg_cost_usd     FLOAT,
    active_from      VARCHAR(40),
    active_until     VARCHAR(40),
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP,
    UNIQUE (agent_id, version)
);

CREATE INDEX IF NOT EXISTS idx_agent_versions_agent_id  ON agent_versions(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_versions_is_active ON agent_versions(is_active);

-- ── leads ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    id                VARCHAR(36)  PRIMARY KEY,
    name              VARCHAR(200) NOT NULL,  -- wide enough for any Unicode (Hebrew, Arabic, etc.)
    city              VARCHAR(120),
    phone             VARCHAR(40),
    email             VARCHAR(200),
    sector            VARCHAR(80),            -- free-text; any sector value is valid (e.g. 'aluminum', 'real_estate')
    source            VARCHAR(60)  NOT NULL DEFAULT 'manual',
    status            VARCHAR(60)  NOT NULL DEFAULT 'חדש',
    score             INTEGER      NOT NULL DEFAULT 0,
    attempts          INTEGER      NOT NULL DEFAULT 0,
    last_contact      VARCHAR(40),
    response          TEXT,
    notes             TEXT,
    assigned_agent_id VARCHAR(36),
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leads_phone  ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_score  ON leads(score);
CREATE INDEX IF NOT EXISTS idx_leads_sector ON leads(sector);

-- Run this once against an existing Railway DB if the table already existed before this migration:
-- ALTER TABLE leads ADD COLUMN IF NOT EXISTS sector VARCHAR(80);
-- ALTER TABLE leads ALTER COLUMN name TYPE VARCHAR(200);
-- ALTER TABLE leads ALTER COLUMN email TYPE VARCHAR(200);
-- ALTER TABLE leads ALTER COLUMN city TYPE VARCHAR(120);

-- ── lead_history ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lead_history (
    id         VARCHAR(36)  PRIMARY KEY,
    lead_id    VARCHAR(36)  NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    action     VARCHAR(120) NOT NULL,
    note       TEXT,
    agent_id   VARCHAR(36),
    model_used VARCHAR(60),
    created_at VARCHAR(40)  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lead_history_lead_id ON lead_history(lead_id);

-- ── tasks ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id              VARCHAR(36)  PRIMARY KEY,
    type            VARCHAR(80)  NOT NULL,
    action          VARCHAR(80)  NOT NULL,
    priority        INTEGER      NOT NULL DEFAULT 5,
    status          VARCHAR(40)  NOT NULL DEFAULT 'created',
    agent_id        VARCHAR(36),
    parent_task_id  VARCHAR(36),
    trace_id        VARCHAR(36),
    input_data      TEXT,                           -- JSON
    output_data     TEXT,                           -- JSON
    risk_level      INTEGER      NOT NULL DEFAULT 1,
    approved_by     VARCHAR(80),
    approval_id     VARCHAR(36),
    model_used      VARCHAR(60),
    tokens_input    INTEGER,
    tokens_output   INTEGER,
    cost_usd        FLOAT,
    retry_count     INTEGER      NOT NULL DEFAULT 0,
    max_retries     INTEGER      NOT NULL DEFAULT 3,
    last_error      TEXT,
    started_at      VARCHAR(40),
    completed_at    VARCHAR(40),
    duration_ms     INTEGER,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_type           ON tasks(type);
CREATE INDEX IF NOT EXISTS idx_tasks_status         ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent_id       ON tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_trace_id       ON tasks(trace_id);

-- ── events ────────────────────────────────────────────────────────────────────
-- Append-only. No UPDATE or DELETE ever issued on this table.
CREATE TABLE IF NOT EXISTS events (
    id               VARCHAR(36)  PRIMARY KEY,
    event_type       VARCHAR(80)  NOT NULL,
    payload          TEXT,                           -- JSON
    source_agent_id  VARCHAR(36),
    source_task_id   VARCHAR(36),
    trace_id         VARCHAR(36),
    created_at       VARCHAR(40)  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_event_type      ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_source_agent_id ON events(source_agent_id);
CREATE INDEX IF NOT EXISTS idx_events_source_task_id  ON events(source_task_id);
CREATE INDEX IF NOT EXISTS idx_events_trace_id        ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at      ON events(created_at);

-- ── memory ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memory (
    id         VARCHAR(36)  PRIMARY KEY,
    namespace  VARCHAR(80)  NOT NULL,
    key        VARCHAR(200) NOT NULL,
    value      TEXT,
    version    INTEGER      NOT NULL DEFAULT 1,
    updated_by VARCHAR(80),
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE (namespace, key)
);

CREATE INDEX IF NOT EXISTS idx_memory_namespace ON memory(namespace);
CREATE INDEX IF NOT EXISTS idx_memory_key       ON memory(key);

-- ── approvals ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS approvals (
    id           VARCHAR(36)  PRIMARY KEY,
    task_id      VARCHAR(36),
    action       VARCHAR(80)  NOT NULL,
    details      TEXT,                               -- JSON
    risk_level   INTEGER      NOT NULL,
    status       VARCHAR(40)  NOT NULL DEFAULT 'pending',
    requested_by VARCHAR(80),
    resolved_by  VARCHAR(80),
    resolved_at  VARCHAR(40),
    note         TEXT,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_approvals_task_id ON approvals(task_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status  ON approvals(status);

-- ── dlq (dead letter queue) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dlq (
    id                VARCHAR(36)  PRIMARY KEY,
    original_task_id  VARCHAR(36)  NOT NULL,
    action            VARCHAR(80)  NOT NULL,
    payload           TEXT,                          -- JSON
    failure_reason    TEXT         NOT NULL,
    attempts_made     INTEGER      NOT NULL DEFAULT 0,
    status            VARCHAR(40)  NOT NULL DEFAULT 'pending_review',
    resolved_at       VARCHAR(40),
    resolved_note     TEXT,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dlq_original_task_id ON dlq(original_task_id);
CREATE INDEX IF NOT EXISTS idx_dlq_status           ON dlq(status);

-- ── traces ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS traces (
    id          VARCHAR(36)   PRIMARY KEY,
    trace_id    VARCHAR(36)   NOT NULL UNIQUE,
    task_id     VARCHAR(36),
    command     VARCHAR(500),
    spans       TEXT          NOT NULL DEFAULT '[]', -- JSON array
    duration_ms INTEGER,
    status      VARCHAR(40)   NOT NULL DEFAULT 'open',
    created_at  VARCHAR(40)   NOT NULL,
    closed_at   VARCHAR(40)
);

CREATE INDEX IF NOT EXISTS idx_traces_trace_id ON traces(trace_id);
CREATE INDEX IF NOT EXISTS idx_traces_task_id  ON traces(task_id);

-- ── goals (Batch 6) ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS goals (
    id             VARCHAR(36)  PRIMARY KEY,
    raw_goal       TEXT         NOT NULL,
    domain         VARCHAR(60)  NOT NULL DEFAULT 'default',
    primary_metric VARCHAR(60)  NOT NULL DEFAULT 'revenue',
    status         VARCHAR(30)  NOT NULL DEFAULT 'active',
    tracks         TEXT,                           -- JSON
    created_at     VARCHAR(40)  NOT NULL,
    updated_at     VARCHAR(40)
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_domain ON goals(domain);

-- ── opportunities (Batch 6) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS opportunities (
    id          VARCHAR(36)  PRIMARY KEY,
    goal_id     VARCHAR(36)  NOT NULL,
    track_id    VARCHAR(36),
    title       TEXT         NOT NULL,
    audience    VARCHAR(60)  NOT NULL DEFAULT 'general',
    channel     VARCHAR(40)  NOT NULL DEFAULT 'whatsapp',
    potential   VARCHAR(20)  NOT NULL DEFAULT 'medium',
    effort      VARCHAR(20)  NOT NULL DEFAULT 'medium',
    next_action TEXT,
    status      VARCHAR(20)  NOT NULL DEFAULT 'open',
    created_at  VARCHAR(40)  NOT NULL,
    updated_at  VARCHAR(40)
);

CREATE INDEX IF NOT EXISTS idx_opportunities_goal_id ON opportunities(goal_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_status  ON opportunities(status);

-- ── outreach_records (Batch 6/8) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS outreach_records (
    id             VARCHAR(36)  PRIMARY KEY,
    goal_id        VARCHAR(36)  NOT NULL,
    opp_id         VARCHAR(36),
    contact_name   VARCHAR(120) NOT NULL,
    contact_phone  VARCHAR(40),
    channel        VARCHAR(40)  NOT NULL DEFAULT 'whatsapp',
    message_body   TEXT,
    status         VARCHAR(30)  NOT NULL DEFAULT 'pending',
    attempt        INTEGER      NOT NULL DEFAULT 1,
    sent_at        VARCHAR(40),
    replied_at     VARCHAR(40),
    next_followup  VARCHAR(40),
    notes          TEXT,
    created_at     VARCHAR(40)  NOT NULL,
    updated_at     VARCHAR(40)
);

CREATE INDEX IF NOT EXISTS idx_outreach_goal_id ON outreach_records(goal_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status  ON outreach_records(status);

-- =============================================================================
-- End of migration 001_initial
-- =============================================================================
