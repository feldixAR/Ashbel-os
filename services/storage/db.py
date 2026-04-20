"""
Database engine, session factory, and lifecycle management.
Supports SQLite (dev) and PostgreSQL (production) transparently.
"""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from config.settings import DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT, DB_ECHO_SQL, ENV, Environment
from services.storage.models.base import Base

log = logging.getLogger(__name__)

# ── Engine factory ────────────────────────────────────────────────────────────
def _build_engine():
    is_sqlite = DATABASE_URL.startswith("sqlite")

    if is_sqlite:
        # SQLite — single-threaded pool, enable WAL for concurrent reads
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=DB_ECHO_SQL,
        )
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        return engine

    # PostgreSQL — connection pool
    return create_engine(
        DATABASE_URL,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_timeout=DB_POOL_TIMEOUT,
        pool_pre_ping=True,          # detect stale connections
        echo=DB_ECHO_SQL,
    )


engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ── Session context manager ───────────────────────────────────────────────────
@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy session, commits on success, rolls back on error.
    Usage:
        with get_session() as session:
            session.add(record)
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Schema management ─────────────────────────────────────────────────────────
def create_all_tables() -> None:
    """Create all tables that don't yet exist. Safe to call on startup."""
    log.info("Creating database tables (if not exist)...")
    # Import all models so SQLAlchemy registers them before create_all
    import services.storage.models.lead        # noqa
    import services.storage.models.task        # noqa
    import services.storage.models.approval    # noqa
    import services.storage.models.agent       # noqa
    import services.storage.models.event       # noqa
    import services.storage.models.trace       # noqa
    import services.storage.models.memory      # noqa
    import services.storage.models.dlq         # noqa
    # Batch 6
    import services.storage.models.goal         # noqa
    import services.storage.models.opportunity  # noqa
    import services.storage.models.outreach     # noqa
    # Axis 6 — distributed idempotency
    import services.storage.models.notification # noqa
    # Batch 10 — learning analytics
    import services.storage.models.analytics    # noqa
    # Batch 11 — Revenue CRM
    import services.storage.models.deal          # noqa
    import services.storage.models.activity      # noqa
    import services.storage.models.message       # noqa
    import services.storage.models.stage_history # noqa
    import services.storage.models.calendar_event # noqa
    # Execution bridge
    import services.storage.models.claude_task    # noqa
    # Phase 12 — Lead Acquisition OS
    import services.storage.models.lead_discovery # noqa
    Base.metadata.create_all(bind=engine)
    _run_column_migrations()
    log.info("Database tables ready.")


def _run_column_migrations() -> None:
    """
    Idempotent column migrations for tables that already exist.
    ADD COLUMN IF NOT EXISTS is safe to run on every startup.
    """
    migrations = [
        # leads
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS email  VARCHAR(200)",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS sector VARCHAR(80)",
        # opportunities — Batch 6 hardening
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS normalized_score    FLOAT",
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS raw_score           FLOAT",
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS success_probability FLOAT",
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS revenue_potential   INTEGER",
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS effort_hours        INTEGER",
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS committee_rank      INTEGER",
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS is_committee_winner BOOLEAN DEFAULT FALSE",
        # goals — Batch 6 hardening
        "ALTER TABLE goals ADD COLUMN IF NOT EXISTS committee_decision       TEXT",
        "ALTER TABLE goals ADD COLUMN IF NOT EXISTS committee_winner_title   VARCHAR(200)",
        "ALTER TABLE goals ADD COLUMN IF NOT EXISTS committee_reasoning      TEXT",
        "ALTER TABLE goals ADD COLUMN IF NOT EXISTS prioritized_actions_json TEXT",
        "ALTER TABLE goals ADD COLUMN IF NOT EXISTS goal_status              VARCHAR(30) DEFAULT 'analyzed'",
        # outreach_records — Batch 8 dispatch tracking
        "ALTER TABLE outreach_records ADD COLUMN IF NOT EXISTS delivery_status     VARCHAR(40)",
        "ALTER TABLE outreach_records ADD COLUMN IF NOT EXISTS failure_reason      TEXT",
        "ALTER TABLE outreach_records ADD COLUMN IF NOT EXISTS provider_message_id VARCHAR(80)",
        # outreach_records — Batch 9 lifecycle FSM
        "ALTER TABLE outreach_records ADD COLUMN IF NOT EXISTS parent_record_id VARCHAR(36)",
        "ALTER TABLE outreach_records ADD COLUMN IF NOT EXISTS lifecycle_status  VARCHAR(30) DEFAULT 'sent'",
        "ALTER TABLE outreach_records ADD COLUMN IF NOT EXISTS next_action_at   VARCHAR(40)",
        # messages — Batch 11 CRM
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS deal_id            VARCHAR(36)",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS subject            VARCHAR(300)",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at_il    VARCHAR(40)",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at_il         VARCHAR(40)",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS raw_payload        TEXT",
        # activities — Batch 11 CRM
        "ALTER TABLE activities ADD COLUMN IF NOT EXISTS deal_id          VARCHAR(36)",
        "ALTER TABLE activities ADD COLUMN IF NOT EXISTS duration_sec     INTEGER",
        "ALTER TABLE activities ADD COLUMN IF NOT EXISTS performed_at_il  VARCHAR(40)",
        # leads — Batch 7 Revenue CRM
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS company          VARCHAR(200)",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS domain           VARCHAR(100)",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS potential_value  INTEGER DEFAULT 0",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS owner            VARCHAR(120)",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_action      TEXT",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_action_due  VARCHAR(40)",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_activity_at VARCHAR(40)",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS priority_score   FLOAT DEFAULT 0",
        # deals — Batch 7 Revenue CRM
        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS expected_profit  INTEGER DEFAULT 0",
        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS commercial_stage VARCHAR(60)",
        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS lost_reason      TEXT",
        # leads — Phase 12 Lead Acquisition OS
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_type          VARCHAR(50)",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_url           TEXT",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS segment              VARCHAR(100)",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_action      VARCHAR(50)",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_draft       TEXT",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS is_inbound           VARCHAR(5) DEFAULT 'false'",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS discovery_session_id VARCHAR(100)",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS meeting_suggested    VARCHAR(5) DEFAULT 'false'",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS geo_fit_score        FLOAT DEFAULT 0",
    # leads — normalise legacy Hebrew status values to English
    "UPDATE leads SET status='new'         WHERE status='\u05d7\u05d3\u05e9'",
    "UPDATE leads SET status='contacted'   WHERE status='\u05e0\u05d9\u05e1\u05d9\u05d5\u05df \u05e7\u05e9\u05e8'",
    "UPDATE leads SET status='hot'         WHERE status='\u05de\u05ea\u05e2\u05d9\u05d9\u05df'",
    "UPDATE leads SET status='closed_won'  WHERE status='\u05e1\u05d2\u05d5\u05e8_\u05d6\u05db\u05d4'",
    "UPDATE leads SET status='closed_lost' WHERE status='\u05e1\u05d2\u05d5\u05e8_\u05d4\u05e4\u05e1\u05d9\u05d3'",
    # Claude bridge — sensitive action flow
        "ALTER TABLE claude_tasks ADD COLUMN IF NOT EXISTS sensitive     BOOLEAN DEFAULT FALSE",
        "ALTER TABLE claude_tasks ADD COLUMN IF NOT EXISTS preview_plan  TEXT",
        # GPT connector — review layer
        "ALTER TABLE claude_tasks ADD COLUMN IF NOT EXISTS review_notes          TEXT",
        # OpenClaw audit tagging
        "ALTER TABLE claude_tasks ADD COLUMN IF NOT EXISTS orchestration_source  VARCHAR(60)",
    ]
    try:
        with engine.begin() as conn:
            for stmt in migrations:
                conn.execute(text(stmt))
        log.info("[DB] Column migrations applied.")
    except Exception as e:
        log.warning(f"[DB] Column migration skipped (likely SQLite): {e}")


def drop_all_tables() -> None:
    """Drop everything — for test teardown only."""
    if ENV == Environment.PRODUCTION:
        raise RuntimeError("drop_all_tables() is forbidden in production.")
    Base.metadata.drop_all(bind=engine)


def health_check() -> bool:
    """Returns True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        log.error(f"Database health check failed: {e}")
        return False
