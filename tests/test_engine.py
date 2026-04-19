from decimal import Decimal

import pytest

from business_rules_genai.actions import BaseActions
from business_rules_genai.engine import (
    check_conditions_recursively,
    execute_math_expression,
    parse_math_expression,
    run,
    run_all,
)
from business_rules_genai.operators import NumericType


class DemoActions(BaseActions):
    def percentage(self, numerator, denominator):
        numerator = numerator.value if isinstance(numerator, NumericType) else numerator
        denominator = (
            denominator.value if isinstance(denominator, NumericType) else denominator
        )
        if not denominator:
            return NumericType(0)
        return NumericType((Decimal(str(numerator)) / Decimal(str(denominator))) * 100)

    def echo(self, value=None):
        return self.set_value_string("none" if value is None else value)

    def ratio(self, *, numerator, denominator):
        return self.divide(numerator, denominator)


@pytest.fixture
def variables():
    return {
        "revenue": 120,
        "cost": 80,
        "segment": "SME",
        "threshold": NumericType(10),
    }


@pytest.fixture
def actions():
    return DemoActions()


def test_check_conditions_recursively_basic_match(variables, actions):
    conditions = {
        "all": [
            {"name": "revenue", "operator": "greater_than", "value": 100},
            {"name": "segment", "operator": "equal_to", "value": "SME"},
        ]
    }

    passed, trace = check_conditions_recursively(conditions, variables, actions)
    assert passed is True
    assert trace[0]["type"] == "all"
    assert trace[0]["result"] is True


def test_value_condition_branches(variables, actions):
    condition = {
        "name": "revenue",
        "operator": "less_than_or_equal_to",
        "value_condition": [
            {
                "conditions": {
                    "all": [
                        {"name": "segment", "operator": "equal_to", "value": "SME"},
                    ]
                },
                "value": 150,
            },
            {
                "conditions": {"all": [{"function": "always_true", "operator": "is_true"}]},
                "value": 90,
            },
        ],
    }

    passed, trace = check_conditions_recursively({"all": [condition]}, variables, actions)
    assert passed is True
    display = trace[0]["children"][0]
    assert display["summary"].startswith("revenue <=")


def test_math_expression_execution(variables, actions):
    expression = "(revenue - cost) / cost"
    ast_tree = parse_math_expression(expression)
    result = execute_math_expression(ast_tree, variables, actions)
    assert isinstance(result, NumericType)
    assert result.value == Decimal("0.5")


def test_run_all_with_actions(variables, actions):
    rules = [
        {
            "conditions": {
                "all": [
                    {"name": "revenue", "operator": "greater_than", "value": 100},
                    {
                        "function": "percentage",
                        "params": ["revenue", "cost"],
                        "operator": "greater_than",
                        "value": 100,
                    },
                ]
            },
            "actions": [{"function": "set_value_string", "params": "eligible"}],
        }
    ]

    triggered, trace = run_all(rules, variables, actions)
    assert triggered is True
    assert trace and trace[0]["type"] == "all"


def test_run_return_action_result(variables, actions):
    rule = {
        "conditions": {
            "all": [
                {"name": "revenue", "operator": "greater_than", "value": 100},
            ]
        },
        "actions": [
            {"function": "set_value_numeric", "params": 200},
        ],
    }

    triggered, result = run(
        rule,
        variables,
        actions,
        return_action_results=True,
    )
    assert triggered is True
    assert isinstance(result, NumericType)
    assert result.value == Decimal(200)


def test_action_params_support_keyword_arguments_and_variable_references():
    rule = {
        "conditions": {
            "all": [
                {
                    "function": "ratio",
                    "params": {
                        "numerator": {"var": "revenue"},
                        "denominator": {"var": "cost"},
                    },
                    "operator": "greater_than",
                    "value": 1,
                },
                {
                    "name": "revenue",
                    "operator": "greater_than",
                    "value": {"var": "threshold"},
                },
            ]
        },
        "actions": [],
    }

    triggered, trace = run_all([rule], {"revenue": 120, "cost": 80, "threshold": 50}, DemoActions())
    assert triggered is True
    assert trace[0]["children"][0]["summary"].startswith("ratio(")


def test_action_params_preserve_none_variable_values():
    rule = {
        "conditions": {
            "all": [
                {
                    "function": "echo",
                    "params": {"value": {"var": "missing_value"}},
                    "operator": "equal_to",
                    "value": "none",
                }
            ]
        },
        "actions": [],
    }

    triggered, _ = run_all([rule], {"missing_value": None}, DemoActions())
    assert triggered is True


def test_missing_explicit_variable_reference_raises():
    rule = {
        "conditions": {
            "all": [
                {
                    "name": "revenue",
                    "operator": "greater_than",
                    "value": {"var": "threshold"},
                }
            ]
        },
        "actions": [],
    }

    with pytest.raises(KeyError):
        run_all([rule], {"revenue": 1}, DemoActions())


def test_value_condition_supports_explicit_variable_references():
    rule = {
        "conditions": {
            "all": [
                {
                    "name": "revenue",
                    "operator": "greater_than",
                    "value_condition": [
                        {
                            "conditions": {
                                "all": [
                                    {
                                        "name": "segment",
                                        "operator": "equal_to",
                                        "value": "SME",
                                    }
                                ]
                            },
                            "value": {"var": "threshold"},
                        }
                    ],
                }
            ]
        },
        "actions": [],
    }

    triggered, _ = run_all(
        [rule],
        {"revenue": 120, "segment": "SME", "threshold": 100},
        DemoActions(),
    )
    assert triggered is True
