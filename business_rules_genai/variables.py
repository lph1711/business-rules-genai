from __future__ import annotations

import inspect
from typing import Any, Dict, List

from .operators import BaseType, BooleanType, NumericType, StringType, get_type_operators
from .utils import fn_name_to_pretty_label

VariableDefinition = Dict[str, Any]


class BaseVariables:
    """Mixin for classes that expose variables to the rules engine."""

    @classmethod
    def get_all_variables(cls, *, include_operators: bool = True) -> List[VariableDefinition]:
        return export_rule_variables(cls, include_operators=include_operators)


def export_rule_variables(
    variable_source: Any,
    *,
    include_operators: bool = True,
) -> List[VariableDefinition]:
    """Return variable metadata for decorated rule variables."""
    variable_class = variable_source if inspect.isclass(variable_source) else variable_source.__class__
    definitions: List[VariableDefinition] = []

    for name, member in inspect.getmembers(variable_class):
        if not getattr(member, "is_rule_variable", False):
            continue

        field_type = member.field_type.name
        definition: VariableDefinition = {
            "name": name,
            "label": getattr(member, "label", None) or fn_name_to_pretty_label(name),
            "field_type": field_type,
            "options": list(getattr(member, "options", [])),
        }

        description = getattr(member, "description", None)
        if description:
            definition["description"] = description

        if include_operators:
            definition["operators"] = get_type_operators(field_type)

        definitions.append(definition)

    return definitions


def rule_variable(
    field_type: type[BaseType],
    label: str | None = None,
    *,
    options: List[Any] | None = None,
    description: str | None = None,
):
    """Decorator to register a method as a UI-discoverable rule variable."""

    normalized_options = list(options or [])

    def wrapper(func):
        if not (type(field_type) == type and issubclass(field_type, BaseType)):
            raise AssertionError(
                f"{field_type} is not instance of BaseType in rule_variable field_type"
            )
        func.field_type = field_type
        func.is_rule_variable = True
        func.label = label or fn_name_to_pretty_label(func.__name__)
        func.options = normalized_options
        func.description = description
        return func

    return wrapper


def _rule_variable_wrapper(
    field_type: type[BaseType],
    label=None,
    *,
    options: List[Any] | None = None,
    description: str | None = None,
):
    if callable(label):
        return rule_variable(field_type, options=options, description=description)(label)
    return rule_variable(
        field_type,
        label=label,
        options=options,
        description=description,
    )


def numeric_rule_variable(label=None, *, options=None, description=None):
    return _rule_variable_wrapper(
        NumericType,
        label,
        options=options,
        description=description,
    )


def string_rule_variable(label=None, *, options=None, description=None):
    return _rule_variable_wrapper(
        StringType,
        label,
        options=options,
        description=description,
    )


def boolean_rule_variable(label=None, *, options=None, description=None):
    return _rule_variable_wrapper(
        BooleanType,
        label,
        options=options,
        description=description,
    )


__all__ = [
    "BaseVariables",
    "boolean_rule_variable",
    "export_rule_variables",
    "numeric_rule_variable",
    "rule_variable",
    "string_rule_variable",
]
