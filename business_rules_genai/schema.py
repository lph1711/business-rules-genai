from __future__ import annotations

from typing import Any, Dict

from .actions import export_rule_actions
from .operators import export_operator_catalog
from .variables import export_rule_variables


def export_rule_schema(variables: Any, actions: Any) -> Dict[str, Any]:
    """Return frontend-oriented metadata for the rules DSL."""
    return {
        "variables": export_rule_variables(variables),
        "actions": export_rule_actions(actions),
        "operators": export_operator_catalog(),
        "condition_groups": ["all", "any"],
        "condition_sources": ["name", "function", "expression", "label"],
        "references": {
            "variable": {"var": "variable_name"},
            "literal": {"literal": "any JSON value"},
        },
    }


__all__ = ["export_rule_schema"]
