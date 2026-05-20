"""Unit tests for Money — pure, no I/O."""

from decimal import Decimal

import pytest

from banking.domain.exceptions import CurrencyMismatchError, InvalidAmountError
from banking.domain.value_objects import Money


class TestMoneyConstruction:
    def test_quantizes_to_two_decimals(self):
        assert Money(Decimal("10.123"), "EUR").amount == Decimal("10.12")

    def test_rejects_float_amount(self):
        with pytest.raises(InvalidAmountError):
            Money(10.0, "EUR")  # type: ignore[arg-type]

    def test_rejects_unknown_currency(self):
        with pytest.raises(InvalidAmountError):
            Money(Decimal("1"), "XXX")

    def test_zero_factory(self):
        z = Money.zero("EUR")
        assert z.amount == Decimal("0.00")
        assert z.currency == "EUR"


class TestMoneyArithmetic:
    def test_add_same_currency(self):
        result = Money(Decimal("10.50"), "EUR") + Money(Decimal("4.25"), "EUR")
        assert result == Money(Decimal("14.75"), "EUR")

    def test_sub_same_currency(self):
        result = Money(Decimal("10.00"), "EUR") - Money(Decimal("3.50"), "EUR")
        assert result == Money(Decimal("6.50"), "EUR")

    def test_add_different_currency_raises(self):
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("1"), "EUR") + Money(Decimal("1"), "USD")

    def test_comparison(self):
        assert Money(Decimal("5"), "EUR") < Money(Decimal("10"), "EUR")
        assert Money(Decimal("5"), "EUR") <= Money(Decimal("5"), "EUR")

    def test_comparison_different_currency_raises(self):
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("1"), "EUR") < Money(Decimal("1"), "USD")
