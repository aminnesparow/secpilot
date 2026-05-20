"""FastAPI app factory."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .api.dependencies import configure_session_factory
from .api.routes_accounts import router as accounts_router
from .api.routes_transfers import router as transfers_router
from .infrastructure.database import make_engine, make_session_factory
from .infrastructure.models import Base


def create_app(engine: Engine | None = None, *, create_schema: bool = False) -> FastAPI:
    engine = engine or make_engine()
    if create_schema:
        Base.metadata.create_all(engine)
    session_factory: sessionmaker = make_session_factory(engine)
    configure_session_factory(session_factory)

    app = FastAPI(title="SecPilot Banking", version="1.0.0")
    app.include_router(accounts_router)
    app.include_router(transfers_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
