"""Unit tests for TransferService — validation and idempotency paths.

Repositories are mocked; database integration is covered separately under
tests/python/banking/integration.
"""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from banking.domain.entities import Account, AccountStatus, Transfer, TransferStatus
from banking.domain.exceptions import (
    CurrencyMismatchError,
    DuplicateTransferError,
    InsufficientFundsError,
    InvalidAmountError,
)
from banking.domain.value_objects import Money
from banking.service import transfer_service as svc_module
from banking.service.transfer_service import TransferService


def _account(currency: str = "EUR", balance: str = "1000.00") -> Account:
    return Account(
        customer_id=uuid4(),
        balance=Money(Decimal(balance), currency),
        status=AccountStatus.ACTIVE,
    )


@pytest.fixture
def mocked_repos(monkeypatch):
    accounts = MagicMock(name="AccountRepository")
    transactions = MagicMock(name="TransactionRepository")
    transfers = MagicMock(name="TransferRepository")
    monkeypatch.setattr(svc_module, "AccountRepository", lambda s: accounts)
    monkeypatch.setattr(svc_module, "TransactionRepository", lambda s: transactions)
    monkeypatch.setattr(svc_module, "TransferRepository", lambda s: transfers)
    return accounts, transactions, transfers


class TestIdempotency:
    def test_returns_existing_transfer_on_replay(self, mocked_repos):
        _, _, transfers = mocked_repos
        source_id, dest_id = uuid4(), uuid4()
        existing = Transfer(
            source_account_id=source_id,
            dest_account_id=dest_id,
            amount=Money(Decimal("100"), "EUR"),
            idempotency_key="abc12345",
            status=TransferStatus.COMPLETED,
        )
        transfers.get_by_idempotency_key.return_value = existing

        service = TransferService(MagicMock())
        result = service.initiate(
            source_id=source_id,
            dest_id=dest_id,
            amount=Money(Decimal("100"), "EUR"),
            idempotency_key="abc12345",
        )

        assert result is existing

    def test_raises_when_idempotency_key_reused_with_different_params(
        self, mocked_repos
    ):
        _, _, transfers = mocked_repos
        existing = Transfer(
            source_account_id=uuid4(),
            dest_account_id=uuid4(),
            amount=Money(Decimal("100"), "EUR"),
            idempotency_key="abc12345",
            status=TransferStatus.COMPLETED,
        )
        transfers.get_by_idempotency_key.return_value = existing

        service = TransferService(MagicMock())
        with pytest.raises(DuplicateTransferError):
            service.initiate(
                source_id=uuid4(),
                dest_id=uuid4(),
                amount=Money(Decimal("50"), "EUR"),
                idempotency_key="abc12345",
            )


class TestValidation:
    def test_rejects_zero_amount(self, mocked_repos):
        _, _, transfers = mocked_repos
        transfers.get_by_idempotency_key.return_value = None

        service = TransferService(MagicMock())
        with pytest.raises(InvalidAmountError):
            service.initiate(
                source_id=uuid4(),
                dest_id=uuid4(),
                amount=Money(Decimal("0"), "EUR"),
                idempotency_key="abcdefgh",
            )

    def test_rejects_same_source_and_dest(self, mocked_repos):
        _, _, transfers = mocked_repos
        transfers.get_by_idempotency_key.return_value = None
        same_id = uuid4()

        service = TransferService(MagicMock())
        with pytest.raises(InvalidAmountError):
            service.initiate(
                source_id=same_id,
                dest_id=same_id,
                amount=Money(Decimal("10"), "EUR"),
                idempotency_key="abcdefgh",
            )

    def test_rejects_currency_mismatch(self, mocked_repos):
        accounts, _, transfers = mocked_repos
        transfers.get_by_idempotency_key.return_value = None
        source = _account(currency="EUR")
        dest = _account(currency="USD")
        accounts.get.side_effect = lambda aid: source if aid == source.id else dest
        accounts.get_for_update.side_effect = lambda aid: (
            source if aid == source.id else dest
        )

        service = TransferService(MagicMock())
        with pytest.raises(CurrencyMismatchError):
            service.initiate(
                source_id=source.id,
                dest_id=dest.id,
                amount=Money(Decimal("10"), "EUR"),
                idempotency_key="abcdefgh",
            )

    def test_rejects_insufficient_funds(self, mocked_repos):
        accounts, _, transfers = mocked_repos
        transfers.get_by_idempotency_key.return_value = None
        source = _account(balance="5.00")
        dest = _account()
        accounts.get.side_effect = lambda aid: source if aid == source.id else dest
        accounts.get_for_update.side_effect = lambda aid: (
            source if aid == source.id else dest
        )

        service = TransferService(MagicMock())
        with pytest.raises(InsufficientFundsError):
            service.initiate(
                source_id=source.id,
                dest_id=dest.id,
                amount=Money(Decimal("100"), "EUR"),
                idempotency_key="abcdefgh",
            )
