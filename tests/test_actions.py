from decimal import Decimal

from business_rules_genai.actions import BaseActions
from business_rules_genai.operators import BooleanType, NumericType, StringType


class DemoActions(BaseActions):
    pass


def test_numeric_helpers_wrap_values():
    actions = DemoActions()
    wrapped = actions.set_value_numeric(10)
    assert isinstance(wrapped, NumericType)
    assert wrapped.value == Decimal(10)

    existing = NumericType(5)
    wrapped_existing = actions.set_value_numeric(existing)
    assert wrapped_existing.value == existing.value


def test_string_and_boolean_helpers():
    actions = DemoActions()
    assert isinstance(actions.set_value_string("hello"), StringType)
    assert isinstance(actions.always_true(), BooleanType)
    assert actions.set_value_none() is None


def test_arithmetic_operations_handle_raw_and_wrapped_inputs():
    actions = DemoActions()
    five = NumericType(5)
    three = NumericType(3)

    assert actions.add(five, three).value == Decimal("8")
    assert actions.minus(10, five).value == Decimal("5")
    assert actions.mult(five, 2).value == Decimal("10")
    assert actions.divide(Decimal("10"), three).value == Decimal("3.333333333333333333333333333")
    assert actions.divide(three, 0).value == Decimal("0")
