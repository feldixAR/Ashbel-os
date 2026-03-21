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
    Base.metadata.create_all(bind=engine)
    log.info("Database tables ready.")


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
