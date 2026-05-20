"""Repository for account transactions (the credit/debit history)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.entities import Transaction, TransactionType
from ..domain.value_objects import Money
from ..infrastructure.models import TransactionModel


def _to_domain(row: TransactionModel) -> Transaction:
    return Transaction(
        id=row.id,
        account_id=row.account_id,
        type=TransactionType(row.type),
        amount=Money(row.amount, row.currency),
        balance_after=Money(row.balance_after, row.currency),
        reference=row.reference,
        created_at=row.created_at,
    )


class TransactionRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, transaction: Transaction) -> Transaction:
        row = TransactionModel(
            id=transaction.id,
            account_id=transaction.account_id,
            type=transaction.type.value,
            amount=transaction.amount.amount,
            currency=transaction.amount.currency,
            balance_after=transaction.balance_after.amount,
            reference=transaction.reference,
            created_at=transaction.created_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_domain(row)

    def list_for_account(
        self, account_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Transaction]:
        stmt = (
            select(TransactionModel)
            .where(TransactionModel.account_id == account_id)
            .order_by(TransactionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(row) for row in self._session.execute(stmt).scalars()]
