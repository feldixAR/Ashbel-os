"""
Central configuration — all values come from environment variables.
No hardcoded secrets. No JSON fallback in production.
"""
import os
from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION  = "production"
    TEST        = "test"


# ── Environment ──────────────────────────────────────────────────────────────
ENV: Environment = Environment(os.getenv("ENVIRONMENT", "development"))
DEBUG: bool      = ENV == Environment.DEVELOPMENT


# ── Application ──────────────────────────────────────────────────────────────
APP_NAME    = "AshbalOS"
APP_VERSION = "2.0.0"
SECRET_KEY  = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
PORT        = int(os.getenv("PORT", 5000))


# ── Company Profile ──────────────────────────────────────────────────────────
COMPANY_NAME    = os.getenv("COMPANY_NAME",    "אשבל אלומיניום")
COMPANY_DOMAIN  = os.getenv("COMPANY_DOMAIN",  "עבודות אלומיניום")
COMPANY_PROFILE = os.getenv("COMPANY_PROFILE",
    "חלונות, דלתות, פרגולות, מסתורי כביסה, גדרות, חיפוי קירות, מבטחים אוטומטיים")
TARGET_CLIENTS  = os.getenv("TARGET_CLIENTS",
    "בעלי בתים פרטיים, קבלנים, אדריכלים, מעצבי פנים, ועדי בתים")


# ── Database ─────────────────────────────────────────────────────────────────
# Production: PostgreSQL via DATABASE_URL (Railway injects this automatically)
# Development: SQLite
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./data/ashbal_dev.db"
)

# Railway injects postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DB_POOL_SIZE     = int(os.getenv("DB_POOL_SIZE",     "5"))
DB_MAX_OVERFLOW  = int(os.getenv("DB_MAX_OVERFLOW",  "10"))
DB_POOL_TIMEOUT  = int(os.getenv("DB_POOL_TIMEOUT",  "30"))
DB_ECHO_SQL      = DEBUG and os.getenv("DB_ECHO_SQL", "false").lower() == "true"


# ── AI Models ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY",    "")


# ── Auth ─────────────────────────────────────────────────────────────────────
SESSION_TOKEN_TTL_HOURS = int(os.getenv("SESSION_TOKEN_TTL_HOURS", "24"))
API_TOKEN_HEADER        = "Authorization"
OWNER_PASSWORD_HASH     = os.getenv("OWNER_PASSWORD_HASH", "")


# ── Retry ────────────────────────────────────────────────────────────────────
RETRY_MAX_AI_CALLS      = int(os.getenv("RETRY_MAX_AI_CALLS",     "3"))
RETRY_MAX_EXTERNAL_API  = int(os.getenv("RETRY_MAX_EXTERNAL_API", "5"))
RETRY_MAX_DB_WRITES     = int(os.getenv("RETRY_MAX_DB_WRITES",    "3"))
RETRY_BASE_DELAY_SEC    = float(os.getenv("RETRY_BASE_DELAY_SEC", "1.0"))


# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL  = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
LOG_FORMAT = "json"   # always structured
LOG_DIR    = "logs"


# ── Scheduler ────────────────────────────────────────────────────────────────
SCHEDULER_TIMEZONE        = os.getenv("SCHEDULER_TIMEZONE", "Asia/Jerusalem")
LEAD_SCORE_INTERVAL_HOURS = int(os.getenv("LEAD_SCORE_INTERVAL_HOURS", "6"))
DAILY_REPORT_HOUR_UTC     = int(os.getenv("DAILY_REPORT_HOUR_UTC",     "6"))
LEARNING_CYCLE_HOUR_UTC   = int(os.getenv("LEARNING_CYCLE_HOUR_UTC",  "0"))


# ── Autonomy / Risk ──────────────────────────────────────────────────────────
AUTO_APPROVE_BELOW_RISK = int(os.getenv("AUTO_APPROVE_BELOW_RISK", "3"))
