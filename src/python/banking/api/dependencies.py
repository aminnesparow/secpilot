"""FastAPI dependencies — wires the request scope to a SQLAlchemy session."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker

_session_factory: sessionmaker[Session] | None = None


def configure_session_factory(factory: sessionmaker[Session]) -> None:
    """Called once at app startup to bind the session factory used by get_session."""
    global _session_factory
    _session_factory = factory


def get_session() -> Iterator[Session]:
    if _session_factory is None:
        raise RuntimeError(
            "session factory is not configured; call configure_session_factory"
        )
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
