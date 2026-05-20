"""Domain entities (framework-free). ORM models live in infrastructure/models.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from .value_objects import Money


class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class TransactionType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class TransferStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Account:
    customer_id: UUID
    balance: Money
    status: AccountStatus = AccountStatus.ACTIVE
    id: UUID = field(default_factory=uuid4)
    version: int = 0
    created_at: datetime = field(default_factory=_now)

    @property
    def currency(self) -> str:
        return self.balance.currency

    def can_debit(self, amount: Money) -> bool:
        return self.status == AccountStatus.ACTIVE and amount <= self.balance


@dataclass(slots=True)
class Transaction:
    account_id: UUID
    type: TransactionType
    amount: Money
    balance_after: Money
    reference: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Transfer:
    source_account_id: UUID
    dest_account_id: UUID
    amount: Money
    idempotency_key: str
    status: TransferStatus = TransferStatus.PENDING
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    completed_at: datetime | None = None
    failure_reason: str | None = None
