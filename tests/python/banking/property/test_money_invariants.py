"""Property-based tests for Money — uses Hypothesis to generate inputs.

These tests assert the algebraic invariants that any sane money implementation
must satisfy. They are the canary that catches float-precision regressions.
"""

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from banking.domain.value_objects import MONEY_QUANT, Money

_amounts = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


@given(_amounts, _amounts)
def test_addition_is_commutative(a, b):
    ma = Money(a, "EUR")
    mb = Money(b, "EUR")
    assert ma + mb == mb + ma


@given(_amounts, _amounts, _amounts)
def test_addition_is_associative(a, b, c):
    ma, mb, mc = Money(a, "EUR"), Money(b, "EUR"), Money(c, "EUR")
    assert (ma + mb) + mc == ma + (mb + mc)


@given(_amounts)
def test_zero_is_additive_identity(a):
    ma = Money(a, "EUR")
    assert ma + Money.zero("EUR") == ma


@given(_amounts, _amounts)
def test_subtraction_is_inverse_of_addition(a, b):
    ma = Money(a, "EUR")
    mb = Money(b, "EUR")
    assert (ma + mb) - mb == ma


@settings(max_examples=5)
@given(st.integers(min_value=1, max_value=10_000))
def test_repeated_cent_addition_matches_integer_arithmetic(n):
    """Adding 0.01 n times must equal n/100 exactly — float arithmetic fails this."""
    one_cent = Money(Decimal("0.01"), "EUR")
    accumulated = Money.zero("EUR")
    for _ in range(n):
        accumulated = accumulated + one_cent
    expected = Money(Decimal(n) * MONEY_QUANT, "EUR")
    assert accumulated == expected
