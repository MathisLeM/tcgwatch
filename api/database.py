"""SQLAlchemy engine, session factory and DB initialisation.

Mirrors Vigilyx app/database.py:
- SQLite (local dev) -> create_all (fast, no migration overhead).
- PostgreSQL (prod)  -> alembic upgrade head (safe schema evolution).
"""
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from api.config import settings

logger = logging.getLogger(__name__)

# SQLite needs check_same_thread=False for FastAPI's threadpool; Postgres doesn't.
_connect_args = (
    {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=not settings.DATABASE_URL.startswith("sqlite"),
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sqlite_sync_columns() -> None:
    """Dev-only: ALTER-ADD any additive model columns missing from existing SQLite
    tables (create_all only creates missing *tables*, never new columns). All such
    columns are nullable, so ADD COLUMN is safe on populated tables."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    existing = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing:
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    coltype = col.type.compile(dialect=engine.dialect)
                    conn.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}')
                    )
                    logger.info("sqlite: added column %s.%s", table.name, col.name)


def init_db() -> None:
    """Initialise the database at startup."""
    # Import all models so SQLAlchemy / Alembic can see the full metadata.
    from api import models  # noqa: F401

    if settings.DATABASE_URL.startswith("sqlite"):
        # Dev: create any missing tables (existing scraper tables are left intact),
        # then add any additive columns the models gained (create_all doesn't ALTER).
        # Production uses Alembic for the same evolution.
        Base.metadata.create_all(bind=engine)
        _sqlite_sync_columns()
        logger.info("SQLite dev DB ready (create_all + column sync)")
    else:
        import os

        from alembic import command
        from alembic.config import Config

        ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        alembic_cfg = Config(os.path.abspath(ini_path))
        alembic_cfg.attributes["skip_logging_config"] = True
        try:
            logger.info("Running Alembic migrations (DB prefix: %s)", settings.DATABASE_URL[:20])
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations complete")
        except Exception as exc:
            logger.error("Alembic migration FAILED: %s", exc, exc_info=True)
            raise
