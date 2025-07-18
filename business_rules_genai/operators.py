import inspect
import re
from functools import wraps

from .fields import (FIELD_TEXT, FIELD_NUMERIC, FIELD_NO_INPUT, FIELD_LIST,
                     FIELD_SELECT, FIELD_SELECT_MULTIPLE)
from .utils import fn_name_to_pretty_label, float_to_decimal
from decimal import Decimal, Inexact, Context

COMPARISON_OPERATOR_MAP = {
    'equal_to': "==",
    'greater_than': ">",
    'greater_than_or_equal_to': ">=",
    'less_than': "<",
    'less_than_or_equal_to': "<=",
    'contains': "in",
    'does_not_contain': "not in",
    'starts_with': "startswith",
    'ends_with': "endswith",
    'matches_regex': "matches_regex",
    'equal_to_case_insensitive': "== (case insensitive)",
    'non_empty': "is not empty",
}

class BaseType(object):
    def __init__(self, value):
        self.value = self._assert_valid_value_and_cast(value)

    def _assert_valid_value_and_cast(self, value):
        raise NotImplemented()

    @classmethod
    def get_all_operators(cls):
        methods = inspect.getmembers(cls)
        return [{'name': m[0],
                 'label': m[1].label,
                 'input_type': m[1].input_type}
                for m in methods if getattr(m[1], 'is_operator', False)]


def export_type(cls):
    """ Decorator to expose the given class to business_rules.export_rule_data. """
    cls.export_in_rule_data = True
    return cls


def type_operator(input_type, label=None,
                  assert_type_for_arguments=True,
                  comparison_type=None):
    """ Decorator to make a function into a type operator.

    - assert_type_for_arguments - if True this patches the operator function
      so that arguments passed to it will have _assert_valid_value_and_cast
      called on them to make type errors explicit.
    """
    def wrapper(func):
        func.is_operator = True
        func.label = label \
            or fn_name_to_pretty_label(func.__name__)
        func.input_type = input_type
        func.comparison_type = comparison_type

        @wraps(func)
        def inner(self, *args, **kwargs):
            if assert_type_for_arguments:
                args = [self._assert_valid_value_and_cast(arg) for arg in args]
                kwargs = dict((k, self._assert_valid_value_and_cast(v))
                              for k, v in kwargs.items())
                if self.value is None or None in args or None in kwargs.values():
                    return False
            return func(self, *args, **kwargs)
        return inner
    return wrapper


@export_type
class StringType(BaseType):

    name = "string"

    def _assert_valid_value_and_cast(self, value):
        if value is None or not isinstance(value, str):
            # raise AssertionError("{0} is not a valid string type.".
            #                      format(value))
            return None
        return value

    @type_operator(FIELD_TEXT)
    def equal_to(self, other_string):
        return self.value == other_string

    @type_operator(FIELD_TEXT, label="Equal To (case insensitive)")
    def equal_to_case_insensitive(self, other_string):
        return self.value.lower() == other_string.lower()

    @type_operator(FIELD_TEXT)
    def starts_with(self, other_string):
        return self.value.startswith(other_string)

    @type_operator(FIELD_TEXT)
    def ends_with(self, other_string):
        return self.value.endswith(other_string)

    @type_operator(FIELD_TEXT)
    def contains(self, other_string):
        return other_string in self.value

    @type_operator(FIELD_TEXT)
    def matches_regex(self, regex):
        return bool(re.search(regex, self.value))

    @type_operator(FIELD_NO_INPUT)
    def non_empty(self):
        return bool(self.value)
    
    @type_operator(FIELD_TEXT, assert_type_for_arguments=False, comparison_type=FIELD_LIST)
    def is_in(self, value_list):
        """ Check if the string is in a list of values. """
        if not isinstance(value_list, list):
            raise ValueError("value_list must be a list")
        return self.value in value_list

@export_type
class NumericType(BaseType):
    EPSILON = Decimal('0.000001')

    name = "numeric"

    @staticmethod
    def _assert_valid_value_and_cast(value):
        if isinstance(value, float):
            return float_to_decimal(value)
        
        if isinstance(value, int):
            return Decimal(value)
        
        if isinstance(value, Decimal):
            return value
        
        else:
            # raise AssertionError("{0} is not a valid numeric type.".
            #                      format(value))
            return None

    @type_operator(FIELD_NUMERIC)
    def equal_to(self, other_numeric):
        return abs(self.value - other_numeric) <= self.EPSILON
        # return self.value == other_numeric

    @type_operator(FIELD_NUMERIC)
    def greater_than(self, other_numeric):
        return (self.value - other_numeric) > self.EPSILON
        # return self.value > other_numeric

    @type_operator(FIELD_NUMERIC)
    def greater_than_or_equal_to(self, other_numeric):
        return self.greater_than(other_numeric) or self.equal_to(other_numeric)

    @type_operator(FIELD_NUMERIC)
    def less_than(self, other_numeric):
        return (other_numeric - self.value) > self.EPSILON
        # return self.value < other_numeric

    @type_operator(FIELD_NUMERIC)
    def less_than_or_equal_to(self, other_numeric):
        return self.less_than(other_numeric) or self.equal_to(other_numeric)
    
    @type_operator(FIELD_NUMERIC, label="Is in range")
    def between(self, lower_bound, upper_bound):
        """ Check if the numeric value is between two bounds (exclusive). """
        return self.greater_than(lower_bound) and \
               self.less_than(upper_bound)

    @type_operator(FIELD_NUMERIC, label="Is In Range equal")
    def between_equal(self, lower_bound, upper_bound):
        """ Check if the numeric value is between two bounds (inclusive). """
        return self.greater_than_or_equal_to(lower_bound) and \
               self.less_than_or_equal_to(upper_bound)
    
@export_type
class BooleanType(BaseType):

    name = "boolean"

    def _assert_valid_value_and_cast(self, value):
        if type(value) != bool:
            # raise AssertionError("{0} is not a valid boolean type".
            #                      format(value))
            return None
        return value

    @type_operator(FIELD_NO_INPUT)
    def is_true(self):
        return self.value

    @type_operator(FIELD_NO_INPUT)
    def is_false(self):
        return not self.value
