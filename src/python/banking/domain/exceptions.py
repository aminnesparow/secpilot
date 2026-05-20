"""Domain exceptions for the banking module."""


class BankingError(Exception):
    """Base class for banking domain errors."""


class AccountNotFoundError(BankingError):
    pass


class AccountFrozenError(BankingError):
    pass


class InsufficientFundsError(BankingError):
    pass


class CurrencyMismatchError(BankingError):
    pass


class InvalidAmountError(BankingError):
    pass


class DuplicateTransferError(BankingError):
    """Raised when an idempotency key has already been processed with different parameters."""


class TransferNotFoundError(BankingError):
    pass
