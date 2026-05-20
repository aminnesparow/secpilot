"""Integration tests for AccountRepository persistence."""

from decimal import Decimal
from uuid import uuid4

import pytest

from banking.domain.entities import Account, AccountStatus
from banking.domain.exceptions import AccountNotFoundError
from banking.domain.value_objects import Money
from banking.repository.account_repository import AccountRepository


def test_add_then_get_round_trip(session):
    repo = AccountRepository(session)
    account = Account(
        customer_id=uuid4(),
        balance=Money(Decimal("250.00"), "EUR"),
        status=AccountStatus.ACTIVE,
    )
    repo.add(account)
    session.commit()

    loaded = repo.get(account.id)
    assert loaded.id == account.id
    assert loaded.balance == account.balance
    assert loaded.status == AccountStatus.ACTIVE


def test_get_unknown_raises(session):
    repo = AccountRepository(session)
    with pytest.raises(AccountNotFoundError):
        repo.get(uuid4())


def test_update_balance_increments_version(session):
    repo = AccountRepository(session)
    account = Account(customer_id=uuid4(), balance=Money(Decimal("100"), "EUR"))
    repo.add(account)
    session.commit()

    repo.update_balance(account.id, Money(Decimal("75.00"), "EUR"))
    session.commit()

    reloaded = repo.get(account.id)
    assert reloaded.balance == Money(Decimal("75.00"), "EUR")
    assert reloaded.version == account.version + 1
