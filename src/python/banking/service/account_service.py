"""Application service for accounts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..domain.entities import Account, AccountStatus, Transaction
from ..domain.value_objects import Money
from ..repository.account_repository import AccountRepository
from ..repository.transaction_repository import TransactionRepository


class AccountService:
    def __init__(self, session: Session):
        self._session = session
        self._accounts = AccountRepository(session)
        self._transactions = TransactionRepository(session)

    def open_account(self, customer_id: UUID, currency: str) -> Account:
        account = Account(
            customer_id=customer_id,
            balance=Money.zero(currency),
            status=AccountStatus.ACTIVE,
        )
        return self._accounts.add(account)

    def get_account(self, account_id: UUID) -> Account:
        return self._accounts.get(account_id)

    def list_transactions(
        self, account_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Transaction]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        return self._transactions.list_for_account(
            account_id, limit=limit, offset=offset
        )
