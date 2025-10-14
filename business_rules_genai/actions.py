from __future__ import annotations

from decimal import Decimal
from typing import Any, Union

from .operators import BooleanType, NumericType, StringType

NumericInput = Union[int, float, Decimal, NumericType]


class BaseActions:
    """Default action implementations consumed by the rules engine.

    Subclass this class to expose additional domain specific actions.
    The helpers below focus on returning the engine's wrapper types so callers
    can compose actions, expressions, and condition values interchangeably.
    """

    @staticmethod
    def _unwrap_numeric(value: NumericInput) -> Decimal:
        """Convert raw numeric inputs into a ``Decimal``."""
        if isinstance(value, NumericType):
            return value.value
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def set_value_numeric(self, value: NumericInput) -> NumericType:
        """Return the provided value wrapped as ``NumericType``."""
        return NumericType(value if not isinstance(value, NumericType) else value.value)

    def set_value_string(self, value: Union[str, StringType]) -> StringType:
        """Return the provided value wrapped as ``StringType``."""
        return value if isinstance(value, StringType) else StringType(str(value))

    def set_value_none(self) -> None:
        """Return ``None`` to explicitly clear a value."""
        return None

    def always_true(self) -> BooleanType:
        """Utility action that always yields ``True``."""
        return BooleanType(True)

    def add(self, value1: NumericInput, value2: NumericInput) -> NumericType:
        """Add two numeric values."""
        return NumericType(self._unwrap_numeric(value1) + self._unwrap_numeric(value2))

    def minus(self, value1: NumericInput, value2: NumericInput) -> NumericType:
        """Subtract ``value2`` from ``value1``."""
        return NumericType(self._unwrap_numeric(value1) - self._unwrap_numeric(value2))

    def mult(self, value1: NumericInput, value2: NumericInput) -> NumericType:
        """Multiply two numeric values."""
        return NumericType(self._unwrap_numeric(value1) * self._unwrap_numeric(value2))

    def divide(self, value1: NumericInput, value2: NumericInput) -> NumericType:
        """Divide ``value1`` by ``value2``. Returns zero when dividing by zero."""
        denominator = self._unwrap_numeric(value2)
        if denominator == 0:
            return NumericType(0)
        numerator = self._unwrap_numeric(value1)
        return NumericType(numerator / denominator)
