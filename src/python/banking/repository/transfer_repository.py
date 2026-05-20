"""Repository for transfers — including idempotency lookups."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.entities import Transfer, TransferStatus
from ..domain.exceptions import TransferNotFoundError
from ..domain.value_objects import Money
from ..infrastructure.models import TransferModel


def _to_domain(row: TransferModel) -> Transfer:
    return Transfer(
        id=row.id,
        source_account_id=row.source_account_id,
        dest_account_id=row.dest_account_id,
        amount=Money(row.amount, row.currency),
        idempotency_key=row.idempotency_key,
        status=TransferStatus(row.status),
        created_at=row.created_at,
        completed_at=row.completed_at,
        failure_reason=row.failure_reason,
    )


class TransferRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, transfer: Transfer) -> Transfer:
        row = TransferModel(
            id=transfer.id,
            source_account_id=transfer.source_account_id,
            dest_account_id=transfer.dest_account_id,
            amount=transfer.amount.amount,
            currency=transfer.amount.currency,
            status=transfer.status.value,
            idempotency_key=transfer.idempotency_key,
            failure_reason=transfer.failure_reason,
            created_at=transfer.created_at,
            completed_at=transfer.completed_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_domain(row)

    def get(self, transfer_id: UUID) -> Transfer:
        row = self._session.get(TransferModel, transfer_id)
        if row is None:
            raise TransferNotFoundError(str(transfer_id))
        return _to_domain(row)

    def get_by_idempotency_key(self, key: str) -> Transfer | None:
        stmt = select(TransferModel).where(TransferModel.idempotency_key == key)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_domain(row) if row else None

    def mark_completed(self, transfer_id: UUID, completed_at: datetime) -> None:
        row = self._session.get(TransferModel, transfer_id)
        if row is None:
            raise TransferNotFoundError(str(transfer_id))
        row.status = TransferStatus.COMPLETED.value
        row.completed_at = completed_at
