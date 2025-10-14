from decimal import Decimal

from business_rules_genai.operators import BooleanType, NumericType, StringType


def test_string_type_operators():
    value = StringType("Hello World")

    assert value.contains("World")
    assert value.starts_with("Hello")
    assert value.ends_with("World")
    assert value.equal_to_case_insensitive("hello world")
    assert value.matches_regex(r"World$")
    assert value.non_empty()
    assert value.is_in(["Hello World", "Goodbye"])


def test_numeric_type_comparisons_and_range():
    number = NumericType(10)

    assert number.greater_than(Decimal("9"))
    assert number.greater_than_or_equal_to(Decimal("10"))
    assert number.less_than(Decimal("11"))
    assert number.less_than_or_equal_to(Decimal("10"))
    assert number.equal_to(Decimal("10"))
    assert number.between(Decimal("5"), Decimal("15"))
    assert number.between_equal(Decimal("10"), Decimal("10"))


def test_boolean_type():
    true_value = BooleanType(True)
    false_value = BooleanType(False)

    assert true_value.is_true()
    assert not true_value.is_false()
    assert false_value.is_false()
    assert not false_value.is_true()
