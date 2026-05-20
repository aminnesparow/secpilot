"""Value objects for the banking domain.

Money is modelled with Decimal so that arithmetic is exact — float arithmetic
is forbidden for monetary values (see property tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Final

from .exceptions import CurrencyMismatchError, InvalidAmountError

SUPPORTED_CURRENCIES: Final[frozenset[str]] = frozenset({"EUR", "USD", "GBP", "CHF"})
MONEY_QUANT: Final[Decimal] = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidAmountError(
                f"Money.amount must be Decimal, got {type(self.amount).__name__}"
            )
        if self.currency not in SUPPORTED_CURRENCIES:
            raise InvalidAmountError(f"Unsupported currency: {self.currency}")
        object.__setattr__(
            self, "amount", self.amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_EVEN)
        )

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(Decimal("0"), currency)

    def _check_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot operate on {self.currency} and {other.currency}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount <= other.amount

    def is_positive(self) -> bool:
        return self.amount > Decimal("0")

    def is_negative(self) -> bool:
        return self.amount < Decimal("0")
