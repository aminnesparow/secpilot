"""SQLAlchemy engine + session factory."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_DEFAULT_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/banking"


def make_engine(url: str | None = None) -> Engine:
    return create_engine(
        url or os.environ.get("DATABASE_URL", _DEFAULT_URL),
        pool_pre_ping=True,
        future=True,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False, future=True
    )


@contextmanager
def transactional(session: Session) -> Iterator[Session]:
    """Wrap a unit of work in a single DB transaction with rollback on error."""
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
