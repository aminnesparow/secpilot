"""Pydantic schemas — wire format only, never used in service/repository layers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OpenAccountRequest(BaseModel):
    customer_id: UUID
    currency: str = Field(min_length=3, max_length=3)


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    currency: str
    balance: Decimal
    status: str
    created_at: datetime


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    type: str
    amount: Decimal
    currency: str
    balance_after: Decimal
    reference: str
    created_at: datetime


class TransferRequest(BaseModel):
    source_account_id: UUID
    dest_account_id: UUID
    amount: Decimal = Field(gt=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_account_id: UUID
    dest_account_id: UUID
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    completed_at: datetime | None
