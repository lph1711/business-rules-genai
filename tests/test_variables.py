from business_rules_genai.actions import BaseActions, rule_action
from business_rules_genai.schema import export_rule_schema
from business_rules_genai.variables import (
    BaseVariables,
    boolean_rule_variable,
    numeric_rule_variable,
    string_rule_variable,
)


class CustomerVariables(BaseVariables):
    def __init__(self, customer):
        self.customer = customer

    @string_rule_variable(label="Customer Segment", options=["SME", "ENT"])
    def customer_segment(self):
        return self.customer["segment"]

    @numeric_rule_variable(description="Annual revenue in USD")
    def revenue(self):
        return self.customer["revenue"]

    @boolean_rule_variable
    def is_priority(self):
        return self.customer["priority"]


class CustomerActions(BaseActions):
    @rule_action(params={"value": "string"}, return_type="string")
    def tag(self, value):
        return self.set_value_string(value)


def test_variable_schema_exports_labels_options_and_operators():
    variables = CustomerVariables.get_all_variables()
    variable_map = {variable["name"]: variable for variable in variables}

    assert variable_map["customer_segment"]["label"] == "Customer Segment"
    assert variable_map["customer_segment"]["options"] == ["SME", "ENT"]
    assert any(
        operator["name"] == "equal_to"
        for operator in variable_map["customer_segment"]["operators"]
    )
    assert variable_map["revenue"]["description"] == "Annual revenue in USD"


def test_export_rule_schema_returns_frontend_metadata():
    schema = export_rule_schema(CustomerVariables, CustomerActions())

    assert schema["condition_groups"] == ["all", "any"]
    assert schema["references"]["variable"] == {"var": "variable_name"}
    assert any(variable["name"] == "revenue" for variable in schema["variables"])
    assert any(action["name"] == "tag" for action in schema["actions"])
