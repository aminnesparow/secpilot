"""SQLAlchemy ORM models — persistence shape, not domain shape."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class AccountModel(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    version: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc
    )

    transactions: Mapped[list["TransactionModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class TransactionModel(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc
    )

    account: Mapped["AccountModel"] = relationship(back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_account_created", "account_id", "created_at"),
    )


class TransferModel(Base):
    __tablename__ = "transfers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    source_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    dest_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_transfers_idempotency_key"),
    )


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc
    )
