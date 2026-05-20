"""Repository for accounts. Translates between ORM and domain entities."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.entities import Account, AccountStatus
from ..domain.exceptions import AccountNotFoundError
from ..domain.value_objects import Money
from ..infrastructure.models import AccountModel


def _to_domain(row: AccountModel) -> Account:
    return Account(
        id=row.id,
        customer_id=row.customer_id,
        balance=Money(row.balance, row.currency),
        status=AccountStatus(row.status),
        version=row.version,
        created_at=row.created_at,
    )


class AccountRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, account: Account) -> Account:
        row = AccountModel(
            id=account.id,
            customer_id=account.customer_id,
            currency=account.currency,
            balance=account.balance.amount,
            status=account.status.value,
            version=account.version,
            created_at=account.created_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_domain(row)

    def get(self, account_id: UUID) -> Account:
        row = self._session.get(AccountModel, account_id)
        if row is None:
            raise AccountNotFoundError(str(account_id))
        return _to_domain(row)

    def get_for_update(self, account_id: UUID) -> Account:
        """Fetch account with SELECT ... FOR UPDATE to prevent concurrent writes.

        Required for the transfer flow — without the row lock, two concurrent
        transfers could read the same balance and double-spend.
        """
        stmt = (
            select(AccountModel).where(AccountModel.id == account_id).with_for_update()
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            raise AccountNotFoundError(str(account_id))
        return _to_domain(row)

    def update_balance(self, account_id: UUID, new_balance: Money) -> None:
        row = self._session.get(AccountModel, account_id)
        if row is None:
            raise AccountNotFoundError(str(account_id))
        row.balance = new_balance.amount
        row.version += 1
