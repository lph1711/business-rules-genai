from __future__ import annotations

import inspect
from decimal import Decimal
from typing import Any, Callable, Dict, List, Union, get_args, get_origin, get_type_hints

from .operators import BooleanType, NumericType, StringType
from .utils import fn_name_to_pretty_label

NumericInput = Union[int, float, Decimal, NumericType]
ActionDefinition = Dict[str, Any]

_EMPTY = inspect.Signature.empty
_RULE_TYPE_ALIASES = {
    NumericType: NumericType.name,
    StringType: StringType.name,
    BooleanType: BooleanType.name,
    int: NumericType.name,
    float: NumericType.name,
    Decimal: NumericType.name,
    str: StringType.name,
    bool: BooleanType.name,
}


def _annotation_to_rule_type(annotation: Any) -> str | None:
    if annotation in (None, _EMPTY, Any):
        return None

    origin = get_origin(annotation)
    if origin is not None:
        mapped_types = {
            rule_type
            for rule_type in (_annotation_to_rule_type(arg) for arg in get_args(annotation))
            if rule_type is not None
        }
        if len(mapped_types) == 1:
            return mapped_types.pop()
        return None

    if annotation in _RULE_TYPE_ALIASES:
        return _RULE_TYPE_ALIASES[annotation]

    if isinstance(annotation, type):
        for candidate, rule_type in _RULE_TYPE_ALIASES.items():
            if isinstance(candidate, type) and issubclass(annotation, candidate):
                return rule_type

    return None


def _serialize_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    return value


def _normalize_action_params(
    signature: inspect.Signature,
    type_hints: Dict[str, Any],
    declared_params: Dict[str, Any] | List[Dict[str, Any]] | None,
) -> List[Dict[str, Any]]:
    parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.name != "self"
    ]

    if declared_params is None:
        normalized: List[Dict[str, Any]] = []
        for parameter in parameters:
            item: Dict[str, Any] = {
                "name": parameter.name,
                "required": parameter.default is _EMPTY,
            }
            field_type = _annotation_to_rule_type(type_hints.get(parameter.name, parameter.annotation))
            if field_type:
                item["field_type"] = field_type
            if parameter.default is not _EMPTY:
                item["default"] = _serialize_default(parameter.default)
            normalized.append(item)
        return normalized

    if isinstance(declared_params, dict):
        normalized = []
        for parameter in parameters:
            declared = declared_params.get(parameter.name)
            item: Dict[str, Any] = {
                "name": parameter.name,
                "required": parameter.default is _EMPTY,
            }
            if isinstance(declared, str):
                item["field_type"] = declared
            elif isinstance(declared, dict):
                item.update(declared)
                item.setdefault("name", parameter.name)
            elif declared is None:
                field_type = _annotation_to_rule_type(
                    type_hints.get(parameter.name, parameter.annotation)
                )
                if field_type:
                    item["field_type"] = field_type
            else:
                raise TypeError("rule_action params must be strings or dictionaries")
            if parameter.default is not _EMPTY:
                item.setdefault("default", _serialize_default(parameter.default))
            normalized.append(item)
        return normalized

    return [dict(item) for item in declared_params]


def rule_action(
    func: Callable[..., Any] | None = None,
    *,
    label: str | None = None,
    params: Dict[str, Any] | List[Dict[str, Any]] | None = None,
    return_type: str | None = None,
):
    """Decorator to attach frontend metadata to a rule action."""

    def decorator(method: Callable[..., Any]) -> Callable[..., Any]:
        method.is_rule_action = True  # type: ignore[attr-defined]
        method.label = label or fn_name_to_pretty_label(method.__name__)  # type: ignore[attr-defined]
        method.rule_action_params = params  # type: ignore[attr-defined]
        method.return_type = return_type  # type: ignore[attr-defined]
        return method

    if func is not None:
        return decorator(func)
    return decorator


def export_rule_actions(action_source: Any) -> List[ActionDefinition]:
    """Return action metadata for a class or action instance."""
    action_class = action_source if inspect.isclass(action_source) else action_source.__class__
    actions: List[ActionDefinition] = []

    for name, member in inspect.getmembers(action_class, predicate=callable):
        if name.startswith("_") or name == "get_all_actions":
            continue

        try:
            type_hints = get_type_hints(member)
        except Exception:
            type_hints = {}

        signature = inspect.signature(member)
        params = _normalize_action_params(
            signature,
            type_hints,
            getattr(member, "rule_action_params", None),
        )
        return_type = getattr(member, "return_type", None) or _annotation_to_rule_type(
            type_hints.get("return", signature.return_annotation)
        )

        action_definition: ActionDefinition = {
            "name": name,
            "label": getattr(member, "label", None) or fn_name_to_pretty_label(name),
            "params": params,
            "param_style": "list_or_dict",
        }

        description = inspect.getdoc(member)
        if description:
            action_definition["description"] = description
        if return_type:
            action_definition["return_type"] = return_type

        actions.append(action_definition)

    return actions


class BaseActions:
    """Default action implementations consumed by the rules engine.

    Subclass this class to expose additional domain specific actions.
    The helpers below focus on returning the engine's wrapper types so callers
    can compose actions, expressions, and condition values interchangeably.
    """

    @classmethod
    def get_all_actions(cls) -> List[ActionDefinition]:
        return export_rule_actions(cls)

    @staticmethod
    def _unwrap_numeric(value: NumericInput) -> Decimal:
        """Convert raw numeric inputs into a ``Decimal``."""
        if isinstance(value, NumericType):
            return value.value
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @rule_action(label="Set Numeric Value", params={"value": NumericType.name}, return_type=NumericType.name)
    def set_value_numeric(self, value: NumericInput) -> NumericType:
        """Return the provided value wrapped as ``NumericType``."""
        return NumericType(value if not isinstance(value, NumericType) else value.value)

    @rule_action(label="Set String Value", params={"value": StringType.name}, return_type=StringType.name)
    def set_value_string(self, value: Union[str, StringType]) -> StringType:
        """Return the provided value wrapped as ``StringType``."""
        return value if isinstance(value, StringType) else StringType(str(value))

    @rule_action(label="Set Empty Value", return_type="none")
    def set_value_none(self) -> None:
        """Return ``None`` to explicitly clear a value."""
        return None

    @rule_action(label="Always True", return_type=BooleanType.name)
    def always_true(self) -> BooleanType:
        """Utility action that always yields ``True``."""
        return BooleanType(True)

    @rule_action(params={"value1": NumericType.name, "value2": NumericType.name}, return_type=NumericType.name)
    def add(self, value1: NumericInput, value2: NumericInput) -> NumericType:
        """Add two numeric values."""
        return NumericType(self._unwrap_numeric(value1) + self._unwrap_numeric(value2))

    @rule_action(params={"value1": NumericType.name, "value2": NumericType.name}, return_type=NumericType.name)
    def minus(self, value1: NumericInput, value2: NumericInput) -> NumericType:
        """Subtract ``value2`` from ``value1``."""
        return NumericType(self._unwrap_numeric(value1) - self._unwrap_numeric(value2))

    @rule_action(params={"value1": NumericType.name, "value2": NumericType.name}, return_type=NumericType.name)
    def mult(self, value1: NumericInput, value2: NumericInput) -> NumericType:
        """Multiply two numeric values."""
        return NumericType(self._unwrap_numeric(value1) * self._unwrap_numeric(value2))

    @rule_action(params={"value1": NumericType.name, "value2": NumericType.name}, return_type=NumericType.name)
    def divide(self, value1: NumericInput, value2: NumericInput) -> NumericType:
        """Divide ``value1`` by ``value2``. Returns zero when dividing by zero."""
        denominator = self._unwrap_numeric(value2)
        if denominator == 0:
            return NumericType(0)
        numerator = self._unwrap_numeric(value1)
        return NumericType(numerator / denominator)


__all__ = [
    "BaseActions",
    "export_rule_actions",
    "rule_action",
]
