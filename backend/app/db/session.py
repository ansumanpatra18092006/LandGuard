from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _sqlalchemy_database_url(url: str) -> str:
    """
    Normalize common PostgreSQL URLs to psycopg v3.

    Examples:
    postgres://...    -> postgresql+psycopg://...
    postgresql://...  -> postgresql+psycopg://...
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]

    return url


DATABASE_URL = _sqlalchemy_database_url(settings.database_url)

is_sqlite = DATABASE_URL.startswith("sqlite")

engine_kwargs = {
    "pool_pre_ping": True,
}

if is_sqlite:
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
    }
else:
    # Keep the application-side pool intentionally small.
    # This is important when using Supabase pooled PostgreSQL,
    # especially on plans with low connection limits.
    engine_kwargs.update(
        {
            "pool_size": 2,
            "max_overflow": 2,
            "pool_timeout": 15,
            "pool_recycle": 300,
        }
    )

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db():
    with SessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise