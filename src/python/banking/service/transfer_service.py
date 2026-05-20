"""Application service for transfers — the core money-moving flow.

Invariants enforced here:
- atomicity: source debit, dest credit, transaction rows, transfer row,
  and audit log are committed in a single DB transaction.
- isolation: source and dest accounts are read with SELECT ... FOR UPDATE
  to serialise concurrent transfers and prevent double-spend.
- idempotency: identical idempotency_key returns the prior result instead
  of re-executing the flow.
- currency: source and dest must share currency (no implicit FX).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from ..domain.entities import Transaction, TransactionType, Transfer, TransferStatus
from ..domain.exceptions import (
    AccountFrozenError,
    CurrencyMismatchError,
    DuplicateTransferError,
    InsufficientFundsError,
    InvalidAmountError,
)
from ..domain.value_objects import Money
from ..infrastructure.database import transactional
from ..infrastructure.models import AuditLogModel
from ..repository.account_repository import AccountRepository
from ..repository.transaction_repository import TransactionRepository
from ..repository.transfer_repository import TransferRepository


class TransferService:
    def __init__(self, session: Session, *, actor: str = "system"):
        self._session = session
        self._actor = actor
        self._accounts = AccountRepository(session)
        self._transactions = TransactionRepository(session)
        self._transfers = TransferRepository(session)

    def initiate(
        self,
        *,
        source_id: UUID,
        dest_id: UUID,
        amount: Money,
        idempotency_key: str,
    ) -> Transfer:
        existing = self._transfers.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if (
                existing.source_account_id != source_id
                or existing.dest_account_id != dest_id
                or existing.amount != amount
            ):
                raise DuplicateTransferError(
                    f"idempotency key {idempotency_key} reused with different parameters"
                )
            return existing

        if not amount.is_positive():
            raise InvalidAmountError("transfer amount must be strictly positive")
        if source_id == dest_id:
            raise InvalidAmountError("source and destination accounts must differ")

        with transactional(self._session):
            first_id, second_id = sorted([source_id, dest_id], key=str)
            self._accounts.get_for_update(first_id)
            self._accounts.get_for_update(second_id)

            source = self._accounts.get(source_id)
            dest = self._accounts.get(dest_id)

            if source.currency != dest.currency:
                raise CurrencyMismatchError(
                    f"source {source.currency} != dest {dest.currency}"
                )
            if source.currency != amount.currency:
                raise CurrencyMismatchError(
                    f"amount currency {amount.currency} != account {source.currency}"
                )
            if source.status.value != "ACTIVE":
                raise AccountFrozenError(f"source account {source_id} not active")
            if dest.status.value != "ACTIVE":
                raise AccountFrozenError(f"dest account {dest_id} not active")
            if not source.can_debit(amount):
                raise InsufficientFundsError(
                    f"account {source_id} balance {source.balance.amount} < {amount.amount}"
                )

            new_source_balance = source.balance - amount
            new_dest_balance = dest.balance + amount
            self._accounts.update_balance(source_id, new_source_balance)
            self._accounts.update_balance(dest_id, new_dest_balance)

            transfer = Transfer(
                source_account_id=source_id,
                dest_account_id=dest_id,
                amount=amount,
                idempotency_key=idempotency_key,
                status=TransferStatus.PENDING,
            )
            stored = self._transfers.add(transfer)

            ref = f"transfer:{stored.id}"
            self._transactions.add(
                Transaction(
                    account_id=source_id,
                    type=TransactionType.DEBIT,
                    amount=amount,
                    balance_after=new_source_balance,
                    reference=ref,
                )
            )
            self._transactions.add(
                Transaction(
                    account_id=dest_id,
                    type=TransactionType.CREDIT,
                    amount=amount,
                    balance_after=new_dest_balance,
                    reference=ref,
                )
            )

            completed_at = datetime.now(timezone.utc)
            self._transfers.mark_completed(stored.id, completed_at)

            self._session.add(
                AuditLogModel(
                    entity_type="Transfer",
                    entity_id=stored.id,
                    action="COMPLETED",
                    actor=self._actor,
                    payload={
                        "source_id": str(source_id),
                        "dest_id": str(dest_id),
                        "amount": str(amount.amount),
                        "currency": amount.currency,
                        "idempotency_key": idempotency_key,
                    },
                )
            )

            stored.status = TransferStatus.COMPLETED
            stored.completed_at = completed_at
            return stored
