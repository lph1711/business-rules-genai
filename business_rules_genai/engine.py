from __future__ import annotations

import ast
import inspect
import logging
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Sequence, Tuple, Union

from .fields import FIELD_LIST, FIELD_NO_INPUT
from .operators import (
    BaseType,
    BooleanType,
    COMPARISON_OPERATOR_MAP,
    NumericType,
    StringType,
)

logger = logging.getLogger(__name__)

Condition = Dict[str, Any]
Action = Dict[str, Any]
TraceNode = Dict[str, Any]
Rule = Dict[str, Any]
RunResult = Tuple[bool, Union[List[TraceNode], Any]]
MISSING = object()


def run_all(
    rule_list: Sequence[Rule],
    defined_variables: Any,
    defined_actions: Any,
    *,
    stop_on_first_trigger: bool = False,
    return_action_results: bool = False,
) -> RunResult:
    """Evaluate a list of rules against the provided context."""
    aggregated_trace: List[TraceNode] = []
    rule_triggered = False

    for rule in rule_list:
        triggered, details = run(
            rule,
            defined_variables,
            defined_actions,
            return_action_results=return_action_results,
        )
        if return_action_results and triggered:
            return True, details

        if isinstance(details, list):
            aggregated_trace.extend(details)
        elif details is not None:
            aggregated_trace.append(details)

        if triggered:
            rule_triggered = True
            if stop_on_first_trigger:
                return True, aggregated_trace

    return rule_triggered, aggregated_trace


def run(
    rule: Rule,
    defined_variables: Any,
    defined_actions: Any,
    *,
    return_action_results: bool = False,
) -> RunResult:
    """Evaluate a single rule."""
    conditions = rule.get("conditions") or {}
    actions = _normalize_actions(rule.get("actions"))

    triggered, trace = check_conditions_recursively(
        conditions,
        defined_variables,
        defined_actions,
    )

    if triggered:
        action_result = do_actions(actions, defined_variables, defined_actions)
        if return_action_results:
            return True, action_result
        return True, trace

    return False, trace


def check_condition(
    condition: Condition,
    defined_variables: Any,
    defined_actions: Any,
) -> Dict[str, Any]:
    """Evaluate a single condition leaf."""
    operator = condition.get("operator")
    comparison_value = condition.get("value")
    value_condition_list = condition.get("value_condition")
    variable: Any = None

    if value_condition_list:
        comparison_value = _resolve_value_condition(
            value_condition_list, defined_variables, defined_actions
        )
    else:
        comparison_value = _resolve_rule_value(comparison_value, defined_variables)

    label = condition.get("label")

    if "expression" in condition:
        expression = condition["expression"]
        structured_expression = parse_math_expression(expression)
        variable = execute_math_expression(
            structured_expression, defined_variables, defined_actions
        )
        label = label or expression
    elif "function" in condition:
        function_name = condition["function"]
        variable = do_actions(
            [
                {
                    "function": function_name,
                    "params": condition.get("params", []),
                }
            ],
            defined_variables,
            defined_actions,
        )
        params = condition.get("params")
        params_str = _format_action_params(params)
        label = label or f"{function_name}({params_str})"
    elif "name" in condition:
        variable = _get_variable_value(defined_variables, condition["name"])
        label = label or condition["name"]
    elif label:
        comparison_value = (
            comparison_value.value
            if isinstance(comparison_value, BaseType)
            else comparison_value
        )
        return {"label": label, "threshold": comparison_value}
    else:
        raise ValueError("Condition must specify 'name', 'function', 'expression', or 'label'.")

    variable_value = variable.value if isinstance(variable, BaseType) else variable
    comparison_value = (
        comparison_value.value if isinstance(comparison_value, BaseType) else comparison_value
    )

    if operator is None:
        raise ValueError("Condition is missing an 'operator'.")

    return {
        "condition_result": _do_operator_comparison(variable, operator, comparison_value),
        "label": label,
        "operator": operator,
        "value": comparison_value,
        "function_result": variable_value,
    }


def parse_math_expression(expression: str) -> Dict[str, Any]:
    """Parse a math expression into a nested dictionary."""
    tree = ast.parse(expression, mode="eval")

    def parse_node(node: ast.AST) -> Any:
        if isinstance(node, ast.BinOp):
            function_name = OPERATOR_MAP.get(type(node.op))
            if function_name is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return {
                "function": function_name,
                "args": [parse_node(node.left), parse_node(node.right)],
            }
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            return node.value
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    return parse_node(tree.body)


def execute_math_expression(
    ast_dict: Any,
    defined_variables: Any,
    defined_actions: Any,
) -> Any:
    """Execute a parsed math expression against the provided context."""
    if isinstance(ast_dict, dict):
        function_name = ast_dict["function"]
        args = [
            execute_math_expression(arg, defined_variables, defined_actions)
            for arg in ast_dict["args"]
        ]
        if any(arg is None for arg in args):
            return None
        return do_actions(
            [{"function": function_name, "params": args}],
            defined_variables,
            defined_actions,
        )

    if isinstance(ast_dict, str):
        value = _lookup_variable_value(defined_variables, ast_dict)
        if value is MISSING or value is None:
            return None
        wrapped_value = _wrap_value(value)
        if isinstance(wrapped_value, BaseType):
            return wrapped_value if wrapped_value.value is not None else None
        return wrapped_value

    return ast_dict


def do_actions(
    actions: Sequence[Action],
    defined_variables: Any,
    defined_actions: Any,
) -> Any:
    """Execute a sequence of actions and return the final result."""
    result: Any = None

    for action in _normalize_actions(actions):
        method_name = action.get("function") or action.get("name")
        if not method_name:
            raise AssertionError("Action is missing a 'function' or 'name'.")

        method = getattr(defined_actions, method_name, None)
        if method is None:
            raise AssertionError(
                f"Action {method_name} is not defined in class {defined_actions.__class__.__name__}"
            )

        processed_args, processed_kwargs = _build_action_arguments(
            action.get("params"),
            defined_variables,
        )

        try:
            inspect.signature(method).bind(*processed_args, **processed_kwargs)
        except TypeError as exc:
            raise AssertionError(
                f"Action {method_name} parameter mismatch: {exc}"
            ) from exc

        logger.debug(
            "Executing action '%s' with args=%s kwargs=%s",
            method_name,
            processed_args,
            processed_kwargs,
        )

        try:
            result = method(*processed_args, **processed_kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"'{method_name}': {exc}") from exc

    return result


def check_conditions_recursively(
    conditions: Condition,
    defined_variables: Any,
    defined_actions: Any,
) -> Tuple[bool, List[TraceNode]]:
    """Recursively evaluate nested rule conditions and provide trace output."""
    passed, trace = _evaluate_condition_block(conditions, defined_variables, defined_actions)
    trace_list = [trace] if trace else []
    return passed, trace_list


def _resolve_value_condition(
    value_conditions: Iterable[Condition],
    defined_variables: Any,
    defined_actions: Any,
) -> Any:
    """Resolve a value based on the first matching condition branch."""
    for branch in value_conditions:
        branch_conditions = branch.get("conditions") or {}
        matched = True
        if branch_conditions:
            matched, _ = check_conditions_recursively(
                branch_conditions, defined_variables, defined_actions
            )
        if matched:
            if "value" in branch:
                return _resolve_rule_value(branch["value"], defined_variables)
            actions = branch.get("actions") or []
            if actions:
                return do_actions(actions, defined_variables, defined_actions)
            return None

    raise RuntimeError("No matching value_condition branch")


def _evaluate_condition_block(
    condition_block: Condition,
    defined_variables: Any,
    defined_actions: Any,
) -> Tuple[bool, TraceNode | None]:
    """Evaluate a branch of the condition tree."""
    if not condition_block:
        return True, None

    if "all" in condition_block:
        children = condition_block["all"]
        if not isinstance(children, list) or not children:
            raise AssertionError("'all' requires a non-empty list of conditions")

        child_nodes: List[TraceNode] = []
        group_passed = True

        for child in children:
            child_passed, child_node = _evaluate_condition_block(
                child, defined_variables, defined_actions
            )
            if child_node is not None:
                child_nodes.append(child_node)
            if not child_passed:
                group_passed = False

        return group_passed, {
            "type": "all",
            "result": group_passed,
            "children": child_nodes,
        }

    if "any" in condition_block:
        children = condition_block["any"]
        if not isinstance(children, list) or not children:
            raise AssertionError("'any' requires a non-empty list of conditions")

        child_nodes = []
        group_passed = False

        for child in children:
            child_passed, child_node = _evaluate_condition_block(
                child, defined_variables, defined_actions
            )
            if child_node is not None:
                child_nodes.append(child_node)
            if child_passed:
                group_passed = True

        return group_passed, {
            "type": "any",
            "result": group_passed,
            "children": child_nodes,
        }

    condition_details = check_condition(condition_block, defined_variables, defined_actions)

    if "condition_result" not in condition_details:
        return True, {
            "type": "display",
            "label": condition_details.get("label"),
            "threshold": condition_details.get("threshold"),
        }

    operator_token = condition_details.get("operator")
    operator = COMPARISON_OPERATOR_MAP.get(operator_token, operator_token)
    label = condition_details.get("label")
    value = condition_details.get("value")
    display_value = "" if value is None else value
    summary = " ".join(
        str(piece)
        for piece in (label, operator, display_value)
        if piece not in (None, "")
    ).strip()

    trace: TraceNode = {
        "type": "condition",
        "label": label,
        "operator": operator,
        "raw_operator": operator_token,
        "value": value,
        "input": condition_details.get("function_result"),
        "result": condition_details.get("condition_result"),
        "summary": summary,
    }

    condition_result = condition_details.get("condition_result")
    passed = condition_result if isinstance(condition_result, bool) else False
    return passed, trace


def _resolve_action_param(param: Any, defined_variables: Any) -> Any:
    """Resolve action parameters, performing variable substitution when possible."""
    if _is_variable_reference(param):
        variable_name = param["var"]
        value = _lookup_variable_value(defined_variables, variable_name)
        if value is MISSING:
            raise KeyError(f"Variable '{variable_name}' is not defined")
        return _wrap_value(value)
    if _is_literal_wrapper(param):
        return param["literal"]
    if isinstance(param, str):
        value = _lookup_variable_value(defined_variables, param)
        return _wrap_value(value) if value is not MISSING else param
    if isinstance(param, list):
        return [_resolve_action_param(item, defined_variables) for item in param]
    if isinstance(param, dict):
        return {key: _resolve_action_param(value, defined_variables) for key, value in param.items()}
    return param


def _build_action_arguments(raw_params: Any, defined_variables: Any) -> Tuple[List[Any], Dict[str, Any]]:
    if raw_params is None:
        return [], {}
    if isinstance(raw_params, list):
        return ([_resolve_action_param(param, defined_variables) for param in raw_params], {})
    if isinstance(raw_params, dict):
        if _is_variable_reference(raw_params) or _is_literal_wrapper(raw_params):
            return ([_resolve_action_param(raw_params, defined_variables)], {})
        return (
            [],
            {
                key: _resolve_action_param(value, defined_variables)
                for key, value in raw_params.items()
            },
        )
    return ([_resolve_action_param(raw_params, defined_variables)], {})


def _normalize_actions(actions: Union[None, Action, Sequence[Action]]) -> List[Action]:
    """Ensure actions are always processed as a list."""
    if actions is None:
        return []
    if isinstance(actions, list):
        return actions
    return [actions]


def _get_variable_value(defined_variables: Any, name: str) -> BaseType | None:
    """Fetch and wrap a variable value from the provided context."""
    value = _lookup_variable_value(defined_variables, name)
    if value is MISSING:
        return None
    wrapped_value = _wrap_value(value)
    return wrapped_value if isinstance(wrapped_value, BaseType) else None


def _lookup_variable_value(defined_variables: Any, name: str) -> Any:
    if isinstance(defined_variables, dict):
        return defined_variables[name] if name in defined_variables else MISSING

    if not hasattr(defined_variables, name):
        return MISSING

    value = getattr(defined_variables, name)
    return value() if callable(value) else value


def _wrap_value(value: Any) -> Any:
    if isinstance(value, BaseType):
        return value
    if isinstance(value, bool):
        return BooleanType(value)
    if isinstance(value, (int, float, Decimal)):
        return NumericType(value)
    if isinstance(value, str):
        return StringType(value)
    return value


def _is_variable_reference(value: Any) -> bool:
    return isinstance(value, dict) and set(value.keys()) == {"var"}


def _is_literal_wrapper(value: Any) -> bool:
    return isinstance(value, dict) and set(value.keys()) == {"literal"}


def _resolve_rule_value(value: Any, defined_variables: Any) -> Any:
    if _is_variable_reference(value):
        variable_name = value["var"]
        resolved_value = _lookup_variable_value(defined_variables, variable_name)
        if resolved_value is MISSING:
            raise KeyError(f"Variable '{variable_name}' is not defined")
        return resolved_value
    if _is_literal_wrapper(value):
        return value["literal"]
    if isinstance(value, list):
        return [_resolve_rule_value(item, defined_variables) for item in value]
    if isinstance(value, dict):
        return {
            key: _resolve_rule_value(item, defined_variables)
            for key, item in value.items()
        }
    return value


def _format_action_params(params: Any) -> str:
    if params is None:
        return ""
    if isinstance(params, list):
        return ", ".join(_format_action_param(param) for param in params)
    if isinstance(params, dict):
        if _is_variable_reference(params) or _is_literal_wrapper(params):
            return _format_action_param(params)
        return ", ".join(
            f"{name}={_format_action_param(param)}" for name, param in params.items()
        )
    return _format_action_param(params)


def _format_action_param(param: Any) -> str:
    if _is_variable_reference(param):
        return str(param["var"])
    if _is_literal_wrapper(param):
        return repr(param["literal"])
    return str(param)


def _do_operator_comparison(
    operator_type: Any,
    operator_name: str,
    comparison_value: Any,
) -> Any:
    """Compare the provided operator against the comparison value."""
    if operator_type is None:
        return None

    if not isinstance(operator_type, BaseType):
        if isinstance(operator_type, bool):
            operator_type = BooleanType(operator_type)
        elif isinstance(operator_type, (int, float, Decimal)):
            operator_type = NumericType(operator_type)
        elif isinstance(operator_type, str):
            operator_type = StringType(operator_type)
        else:
            raise AssertionError(
                f"Operator {operator_name} is not available for type {type(operator_type).__name__}"
            )

    method = getattr(operator_type, operator_name, None)
    if method is None:
        raise AssertionError(
            f"Operator {operator_name} does not exist for type {operator_type.__class__.__name__}"
        )

    if getattr(method, "input_type", None) == FIELD_NO_INPUT:
        return method()

    if comparison_value is None:
        return None

    if isinstance(comparison_value, BaseType):
        comparison_value = comparison_value.value

    if getattr(method, "comparison_type", None) == FIELD_LIST:
        return method(comparison_value)

    if isinstance(comparison_value, list):
        return method(*comparison_value)

    return method(comparison_value)


OPERATOR_MAP = {
    ast.Add: "add",
    ast.Sub: "minus",
    ast.Mult: "mult",
    ast.Div: "divide",
}


__all__ = [
    "run_all",
    "run",
    "check_conditions_recursively",
    "check_condition",
    "parse_math_expression",
    "execute_math_expression",
    "do_actions",
]
