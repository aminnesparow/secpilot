"""Unit tests for AccountService — pagination boundary validation."""

import pytest

from banking.service.account_service import AccountService


class TestPaginationValidation:
    def test_rejects_limit_below_min(self):
        service = AccountService.__new__(AccountService)
        service._transactions = None  # type: ignore[assignment]
        with pytest.raises(ValueError):
            service.list_transactions(account_id=None, limit=0)  # type: ignore[arg-type]

    def test_rejects_limit_above_max(self):
        service = AccountService.__new__(AccountService)
        service._transactions = None  # type: ignore[assignment]
        with pytest.raises(ValueError):
            service.list_transactions(account_id=None, limit=101)  # type: ignore[arg-type]

    def test_rejects_negative_offset(self):
        service = AccountService.__new__(AccountService)
        service._transactions = None  # type: ignore[assignment]
        with pytest.raises(ValueError):
            service.list_transactions(account_id=None, limit=10, offset=-1)  # type: ignore[arg-type]
