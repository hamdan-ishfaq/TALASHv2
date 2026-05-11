import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.models.models import Base

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://talash:talash@db:5432/talash"
)

_pool_size = int(os.getenv("SQLALCHEMY_POOL_SIZE", "5") or "5")
_max_overflow = int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "10") or "10")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=max(1, min(_pool_size, 20)),
    max_overflow=max(0, min(_max_overflow, 30)),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Lightweight ALTERs for existing deployments (create_all does not add columns).
_OPTIONAL_COLUMNS: list[tuple[str, str, str]] = [
    ("candidates", "target_job_description", "TEXT"),
    ("candidate_assessments", "jd_alignment_score", "DOUBLE PRECISION"),
]


def ensure_optional_columns() -> None:
    try:
        inspector = inspect(engine)
    except Exception as exc:
        logger.warning("ensure_optional_columns skipped: %s", exc)
        return
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, col, coltype in _OPTIONAL_COLUMNS:
            if table not in existing_tables:
                continue
            have = {c["name"] for c in inspector.get_columns(table)}
            if col in have:
                continue
            logger.info("Adding missing column %s.%s", table, col)
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype}"))
            except Exception as exc:
                logger.error("Failed to add column %s.%s: %s", table, col, exc)


def create_all_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_optional_columns()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
