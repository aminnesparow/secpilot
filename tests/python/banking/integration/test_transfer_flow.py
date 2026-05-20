"""End-to-end integration tests for the transfer flow."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from banking.domain.entities import Account, AccountStatus, TransferStatus
from banking.domain.exceptions import (
    CurrencyMismatchError,
    InsufficientFundsError,
)
from banking.domain.value_objects import Money
from banking.repository.account_repository import AccountRepository
from banking.service.transfer_service import TransferService


def _open(session: Session, balance: str, currency: str = "EUR") -> UUID:
    repo = AccountRepository(session)
    account = Account(
        customer_id=uuid4(),
        balance=Money(Decimal(balance), currency),
        status=AccountStatus.ACTIVE,
    )
    repo.add(account)
    session.commit()
    return account.id


def test_happy_path_moves_funds_and_records_history(session):
    source = _open(session, "500.00")
    dest = _open(session, "0.00")

    service = TransferService(session, actor="alice@example.com")
    transfer = service.initiate(
        source_id=source,
        dest_id=dest,
        amount=Money(Decimal("125.50"), "EUR"),
        idempotency_key="ipk-happy-001",
    )

    assert transfer.status == TransferStatus.COMPLETED
    assert transfer.completed_at is not None

    accounts = AccountRepository(session)
    assert accounts.get(source).balance == Money(Decimal("374.50"), "EUR")
    assert accounts.get(dest).balance == Money(Decimal("125.50"), "EUR")

    tx_count = session.execute(text("SELECT COUNT(*) FROM transactions")).scalar_one()
    assert tx_count == 2

    audit_count = session.execute(
        text("SELECT COUNT(*) FROM audit_log WHERE entity_type = 'Transfer'")
    ).scalar_one()
    assert audit_count == 1


def test_idempotent_replay_returns_same_transfer(session):
    source = _open(session, "500.00")
    dest = _open(session, "0.00")

    service = TransferService(session)
    first = service.initiate(
        source_id=source,
        dest_id=dest,
        amount=Money(Decimal("50"), "EUR"),
        idempotency_key="ipk-replay-001",
    )
    second = service.initiate(
        source_id=source,
        dest_id=dest,
        amount=Money(Decimal("50"), "EUR"),
        idempotency_key="ipk-replay-001",
    )

    assert first.id == second.id
    accounts = AccountRepository(session)
    assert accounts.get(source).balance == Money(Decimal("450.00"), "EUR")
    assert accounts.get(dest).balance == Money(Decimal("50.00"), "EUR")


def test_currency_mismatch_aborts_transfer(session):
    source = _open(session, "500.00", currency="EUR")
    dest = _open(session, "0.00", currency="USD")

    service = TransferService(session)
    with pytest.raises(CurrencyMismatchError):
        service.initiate(
            source_id=source,
            dest_id=dest,
            amount=Money(Decimal("10"), "EUR"),
            idempotency_key="ipk-curr-001",
        )

    accounts = AccountRepository(session)
    assert accounts.get(source).balance == Money(Decimal("500.00"), "EUR")
    assert accounts.get(dest).balance == Money(Decimal("0.00"), "USD")


def test_insufficient_funds_aborts_transfer(session):
    source = _open(session, "5.00")
    dest = _open(session, "0.00")

    service = TransferService(session)
    with pytest.raises(InsufficientFundsError):
        service.initiate(
            source_id=source,
            dest_id=dest,
            amount=Money(Decimal("10"), "EUR"),
            idempotency_key="ipk-funds-001",
        )

    accounts = AccountRepository(session)
    assert accounts.get(source).balance == Money(Decimal("5.00"), "EUR")
    assert accounts.get(dest).balance == Money(Decimal("0.00"), "EUR")


def test_concurrent_transfers_serialise_via_row_lock(
    session, session_factory: sessionmaker[Session]
):
    """Two simultaneous transfers from the same account must not double-spend.

    Without SELECT ... FOR UPDATE on the source account, both threads could read
    the same balance and each succeed, debiting twice. With the lock, one of
    them must observe the post-debit balance and fail with InsufficientFunds.
    """
    source = _open(session, "100.00")
    dest_a = _open(session, "0.00")
    dest_b = _open(session, "0.00")

    def _run(dest_id: UUID, key: str) -> str:
        s = session_factory()
        try:
            svc = TransferService(s)
            svc.initiate(
                source_id=source,
                dest_id=dest_id,
                amount=Money(Decimal("80"), "EUR"),
                idempotency_key=key,
            )
            return "ok"
        except InsufficientFundsError:
            return "rejected"
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run, dest_a, "ipk-race-1")
        f2 = pool.submit(_run, dest_b, "ipk-race-2")
        results = {f1.result(), f2.result()}

    assert results == {"ok", "rejected"}, results

    accounts = AccountRepository(session)
    total = (
        accounts.get(source).balance.amount
        + accounts.get(dest_a).balance.amount
        + accounts.get(dest_b).balance.amount
    )
    assert total == Decimal("100.00"), f"conservation violated: total={total}"
