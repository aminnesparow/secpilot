"""FastAPI routes for transfer resources."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..domain.exceptions import (
    AccountFrozenError,
    AccountNotFoundError,
    CurrencyMismatchError,
    DuplicateTransferError,
    InsufficientFundsError,
    InvalidAmountError,
    TransferNotFoundError,
)
from ..domain.value_objects import Money
from ..service.transfer_service import TransferService
from .dependencies import get_session
from .schemas import TransferRequest, TransferResponse

router = APIRouter(prefix="/transfers", tags=["transfers"])


def _to_response(transfer) -> TransferResponse:
    return TransferResponse(
        id=transfer.id,
        source_account_id=transfer.source_account_id,
        dest_account_id=transfer.dest_account_id,
        amount=transfer.amount.amount,
        currency=transfer.amount.currency,
        status=transfer.status.value,
        created_at=transfer.created_at,
        completed_at=transfer.completed_at,
    )


@router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def initiate_transfer(
    body: TransferRequest,
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=64
    ),
    session: Session = Depends(get_session),
) -> TransferResponse:
    service = TransferService(session)
    try:
        transfer = service.initiate(
            source_id=body.source_account_id,
            dest_id=body.dest_account_id,
            amount=Money(body.amount, body.currency),
            idempotency_key=idempotency_key,
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (CurrencyMismatchError, InvalidAmountError, AccountFrozenError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DuplicateTransferError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(transfer)


@router.get("/{transfer_id}", response_model=TransferResponse)
def get_transfer(
    transfer_id: UUID, session: Session = Depends(get_session)
) -> TransferResponse:
    from ..repository.transfer_repository import TransferRepository

    repo = TransferRepository(session)
    try:
        transfer = repo.get(transfer_id)
    except TransferNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(transfer)
