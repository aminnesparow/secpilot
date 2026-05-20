"""FastAPI routes for account resources."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..domain.exceptions import AccountNotFoundError
from ..service.account_service import AccountService
from .dependencies import get_session
from .schemas import AccountResponse, OpenAccountRequest, TransactionResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _to_account_response(account) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        customer_id=account.customer_id,
        currency=account.currency,
        balance=account.balance.amount,
        status=account.status.value,
        created_at=account.created_at,
    )


def _to_transaction_response(tx) -> TransactionResponse:
    return TransactionResponse(
        id=tx.id,
        account_id=tx.account_id,
        type=tx.type.value,
        amount=tx.amount.amount,
        currency=tx.amount.currency,
        balance_after=tx.balance_after.amount,
        reference=tx.reference,
        created_at=tx.created_at,
    )


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def open_account(
    body: OpenAccountRequest, session: Session = Depends(get_session)
) -> AccountResponse:
    service = AccountService(session)
    account = service.open_account(body.customer_id, body.currency)
    session.commit()
    return _to_account_response(account)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: UUID, session: Session = Depends(get_session)
) -> AccountResponse:
    service = AccountService(session)
    try:
        account = service.get_account(account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_account_response(account)


@router.get("/{account_id}/transactions", response_model=list[TransactionResponse])
def list_transactions(
    account_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> list[TransactionResponse]:
    service = AccountService(session)
    txs = service.list_transactions(account_id, limit=limit, offset=offset)
    return [_to_transaction_response(tx) for tx in txs]
