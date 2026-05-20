"""End-to-end API tests using FastAPI TestClient + the real Postgres container."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from banking.app import create_app


@pytest.fixture()
def client(engine):
    app = create_app(engine, create_schema=False)
    return TestClient(app)


def _open(client: TestClient, currency: str = "EUR") -> str:
    r = client.post(
        "/accounts", json={"customer_id": str(uuid4()), "currency": currency}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _seed_balance(session, account_id: str, amount: str) -> None:
    from banking.domain.value_objects import Money
    from banking.repository.account_repository import AccountRepository
    from uuid import UUID

    repo = AccountRepository(session)
    repo.update_balance(UUID(account_id), Money(Decimal(amount), "EUR"))
    session.commit()


def test_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}


def test_open_and_get_account(client: TestClient):
    account_id = _open(client)
    r = client.get(f"/accounts/{account_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "EUR"
    assert Decimal(body["balance"]) == Decimal("0.00")


def test_transfer_happy_path_via_api(client: TestClient, session):
    src = _open(client)
    dst = _open(client)
    _seed_balance(session, src, "200.00")

    r = client.post(
        "/transfers",
        headers={"Idempotency-Key": "ipk-api-happy-001"},
        json={
            "source_account_id": src,
            "dest_account_id": dst,
            "amount": "75.25",
            "currency": "EUR",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"

    assert Decimal(client.get(f"/accounts/{src}").json()["balance"]) == Decimal(
        "124.75"
    )
    assert Decimal(client.get(f"/accounts/{dst}").json()["balance"]) == Decimal("75.25")


def test_transfer_insufficient_funds_returns_422(client: TestClient):
    src = _open(client)
    dst = _open(client)

    r = client.post(
        "/transfers",
        headers={"Idempotency-Key": "ipk-api-funds-001"},
        json={
            "source_account_id": src,
            "dest_account_id": dst,
            "amount": "10.00",
            "currency": "EUR",
        },
    )
    assert r.status_code == 422, r.text


def test_transfer_idempotency_replay(client: TestClient, session):
    src = _open(client)
    dst = _open(client)
    _seed_balance(session, src, "100.00")

    body = {
        "source_account_id": src,
        "dest_account_id": dst,
        "amount": "30.00",
        "currency": "EUR",
    }
    headers = {"Idempotency-Key": "ipk-api-replay-001"}

    first = client.post("/transfers", headers=headers, json=body)
    second = client.post("/transfers", headers=headers, json=body)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert Decimal(client.get(f"/accounts/{src}").json()["balance"]) == Decimal("70.00")
