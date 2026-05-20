"""Integration test fixtures — provision a real Postgres via testcontainers.

These tests require Docker. If Docker (or testcontainers) is unavailable, the
whole module is skipped so unit/property tests still run.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

try:
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-not-found]
except Exception as exc:  # pragma: no cover - import guard
    pytest.skip(f"testcontainers not available: {exc}", allow_module_level=True)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    try:
        with PostgresContainer("postgres:16-alpine") as container:
            url = container.get_connection_url()
            yield url.replace("postgresql://", "postgresql+psycopg2://")
    except Exception as exc:  # pragma: no cover - Docker unavailable
        pytest.skip(f"Docker / postgres container unavailable: {exc}")


@pytest.fixture(scope="session")
def engine(postgres_url: str) -> Iterator[Engine]:
    from banking.infrastructure.database import make_engine
    from banking.infrastructure.models import Base

    eng = make_engine(postgres_url)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    from banking.infrastructure.database import make_session_factory

    return make_session_factory(engine)


@pytest.fixture()
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _truncate_between_tests(engine: Engine) -> Iterator[None]:
    yield
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE audit_log, transactions, transfers, accounts RESTART IDENTITY"
            )
        )
