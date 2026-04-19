from __future__ import annotations

import inspect
import re
from decimal import Decimal
from functools import wraps
from typing import Any, Callable, Dict, Iterable

from .fields import FIELD_LIST, FIELD_NO_INPUT, FIELD_NUMERIC, FIELD_TEXT
from .utils import fn_name_to_pretty_label

COMPARISON_OPERATOR_MAP: Dict[str, str] = {
    "equal_to": "==",
    "greater_than": ">",
    "greater_than_or_equal_to": ">=",
    "less_than": "<",
    "less_than_or_equal_to": "<=",
    "contains": "in",
    "does_not_contain": "not in",
    "starts_with": "startswith",
    "ends_with": "endswith",
    "matches_regex": "matches_regex",
    "equal_to_case_insensitive": "== (case insensitive)",
    "non_empty": "is not empty",
}


class BaseType:
    """Base wrapper class used by the rules engine for type-specific operators."""

    name: str = "base"

    def __init__(self, value: Any) -> None:
        self.value = self._assert_valid_value_and_cast(value)

    def _assert_valid_value_and_cast(self, value: Any) -> Any:
        """Validate the provided value and coerce it into the right shape."""
        raise NotImplementedError


def type_operator(
    input_type: str,
    label: str | None = None,
    *,
    assert_type_for_arguments: bool = True,
    comparison_type: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to mark instance methods as safe operators for the engine."""

    def wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
        func.is_operator = True  # type: ignore[attr-defined]
        func.label = label  # type: ignore[attr-defined]
        func.input_type = input_type  # type: ignore[attr-defined]
        func.comparison_type = comparison_type  # type: ignore[attr-defined]

        @wraps(func)
        def inner(self: BaseType, *args: Any, **kwargs: Any) -> Any:
            if assert_type_for_arguments:
                args = tuple(self._assert_valid_value_and_cast(arg) for arg in args)
                kwargs = {
                    key: self._assert_valid_value_and_cast(value)
                    for key, value in kwargs.items()
                }
                if (
                    self.value is None
                    or any(arg is None for arg in args)
                    or any(value is None for value in kwargs.values())
                ):
                    return False
            return func(self, *args, **kwargs)

        return inner

    return wrapper


class StringType(BaseType):
    """Wrapper class exposing string specific operators."""

    name = "string"

    def _assert_valid_value_and_cast(self, value: Any) -> str | None:
        if value is None or not isinstance(value, str):
            return None
        return value

    @type_operator(FIELD_TEXT)
    def equal_to(self, other_string: str) -> bool:
        return self.value == other_string

    @type_operator(FIELD_TEXT, label="Equal To (case insensitive)")
    def equal_to_case_insensitive(self, other_string: str) -> bool:
        return self.value.lower() == other_string.lower()

    @type_operator(FIELD_TEXT)
    def starts_with(self, other_string: str) -> bool:
        return self.value.startswith(other_string)

    @type_operator(FIELD_TEXT)
    def ends_with(self, other_string: str) -> bool:
        return self.value.endswith(other_string)

    @type_operator(FIELD_TEXT)
    def contains(self, other_string: str) -> bool:
        return other_string in self.value

    @type_operator(FIELD_TEXT)
    def matches_regex(self, regex: str) -> bool:
        return bool(re.search(regex, self.value))

    @type_operator(FIELD_NO_INPUT)
    def non_empty(self) -> bool:
        return bool(self.value)

    @type_operator(
        FIELD_TEXT,
        assert_type_for_arguments=False,
        comparison_type=FIELD_LIST,
    )
    def is_in(self, value_list: Iterable[str]) -> bool:
        """Check if the string is part of a provided list."""
        if isinstance(value_list, str) or not isinstance(value_list, Iterable):
            raise ValueError("value_list must be an iterable of strings")
        return self.value in value_list


class NumericType(BaseType):
    """Wrapper class exposing numeric operators leveraging ``Decimal`` math."""

    EPSILON = Decimal("0.000001")
    name = "numeric"

    def _assert_valid_value_and_cast(self, value: Any) -> Decimal | None:
        if isinstance(value, NumericType):
            return value.value
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, float):
            # Preserve precision by routing through ``str``.
            return Decimal(str(value))
        return None

    @type_operator(FIELD_NUMERIC)
    def equal_to(self, other_numeric: Decimal) -> bool:
        return abs(self.value - other_numeric) <= self.EPSILON

    @type_operator(FIELD_NUMERIC)
    def greater_than(self, other_numeric: Decimal) -> bool:
        return (self.value - other_numeric) > self.EPSILON

    @type_operator(FIELD_NUMERIC)
    def greater_than_or_equal_to(self, other_numeric: Decimal) -> bool:
        return self.greater_than(other_numeric) or self.equal_to(other_numeric)

    @type_operator(FIELD_NUMERIC)
    def less_than(self, other_numeric: Decimal) -> bool:
        return (other_numeric - self.value) > self.EPSILON

    @type_operator(FIELD_NUMERIC)
    def less_than_or_equal_to(self, other_numeric: Decimal) -> bool:
        return self.less_than(other_numeric) or self.equal_to(other_numeric)

    @type_operator(FIELD_NUMERIC, label="Is in range")
    def between(self, lower_bound: Decimal, upper_bound: Decimal) -> bool:
        """Check if the numeric value is between two exclusive bounds."""
        return self.greater_than(lower_bound) and self.less_than(upper_bound)

    @type_operator(FIELD_NUMERIC, label="Is In Range equal")
    def between_equal(self, lower_bound: Decimal, upper_bound: Decimal) -> bool:
        """Check if the numeric value is between two inclusive bounds."""
        return self.greater_than_or_equal_to(lower_bound) and self.less_than_or_equal_to(
            upper_bound
        )


class BooleanType(BaseType):
    """Wrapper class exposing boolean operators."""

    name = "boolean"

    def _assert_valid_value_and_cast(self, value: Any) -> bool | None:
        if isinstance(value, BooleanType):
            return value.value
        if isinstance(value, bool):
            return value
        return None

    @type_operator(FIELD_NO_INPUT)
    def is_true(self) -> bool:
        return bool(self.value)

    @type_operator(FIELD_NO_INPUT)
    def is_false(self) -> bool:
        return not bool(self.value)


TYPE_CLASS_MAP: Dict[str, type[BaseType]] = {
    StringType.name: StringType,
    NumericType.name: NumericType,
    BooleanType.name: BooleanType,
}


def _coerce_type_class(field_type: str | type[BaseType]) -> type[BaseType]:
    if isinstance(field_type, str):
        if field_type not in TYPE_CLASS_MAP:
            raise KeyError(f"Unknown field type: {field_type}")
        return TYPE_CLASS_MAP[field_type]
    return field_type


def get_type_operators(field_type: str | type[BaseType]) -> list[Dict[str, Any]]:
    """Return operator metadata for a field type."""
    type_class = _coerce_type_class(field_type)
    operators: list[Dict[str, Any]] = []

    for name, member in inspect.getmembers(type_class, predicate=callable):
        if not getattr(member, "is_operator", False):
            continue

        operator_label = getattr(member, "label", None) or fn_name_to_pretty_label(name)
        input_type = getattr(member, "input_type", None)
        operators.append(
            {
                "name": name,
                "label": operator_label,
                "field_type": type_class.name,
                "input_type": input_type,
                "comparison_type": getattr(member, "comparison_type", None),
                "requires_value": input_type != FIELD_NO_INPUT,
                "display": COMPARISON_OPERATOR_MAP.get(name, operator_label),
            }
        )

    return operators


def export_operator_catalog() -> Dict[str, list[Dict[str, Any]]]:
    """Return all operators grouped by field type."""
    return {
        field_type: get_type_operators(type_class)
        for field_type, type_class in TYPE_CLASS_MAP.items()
    }


__all__ = [
    "BaseType",
    "BooleanType",
    "COMPARISON_OPERATOR_MAP",
    "NumericType",
    "StringType",
    "export_operator_catalog",
    "get_type_operators",
]
