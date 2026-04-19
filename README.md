# business-rules-genai

Modernised business rules engine with a JSON-friendly DSL and pluggable actions.

## Quick start

```python
from dataclasses import dataclass

from business_rules_genai.actions import BaseActions
from business_rules_genai.engine import run_all


@dataclass
class Customer:
    revenue: int
    cost: int
    segment: str


class CustomerActions(BaseActions):
    def margin(self, revenue, cost):
        revenue = revenue.value if hasattr(revenue, \"value\") else revenue
        cost = cost.value if hasattr(cost, \"value\") else cost
        if not cost:
            return self.set_value_numeric(0)
        return self.set_value_numeric((revenue - cost) / cost)


customer = Customer(revenue=125, cost=50, segment=\"SME\")
actions = CustomerActions()

rule = {
    \"conditions\": {
        \"all\": [
            {\"name\": \"revenue\", \"operator\": \"greater_than\", \"value\": 100},
            {
                \"function\": \"margin\",
                \"params\": [\"revenue\", \"cost\"],
                \"operator\": \"greater_than_or_equal_to\",
                \"value\": 1,
            },
        ]
    },
    \"actions\": [{\"function\": \"set_value_string\", \"params\": \"preferred\"}],
}

triggered, trace = run_all([rule], vars(customer), actions)
print(triggered)  # True
```

The engine accepts either dictionaries or attribute-bearing objects for variables. Actions are regular Python methods that should return one of the wrapper types (`NumericType`, `StringType`, `BooleanType`) already provided by the package.

## Rule building blocks

### Variables

Access variables by name. The engine automatically wraps raw values into the appropriate operator types:

```json
{\"name\": \"revenue\", \"operator\": \"greater_than\", \"value\": 100}
```

If you need to show static information in the UI you can provide a labelled block without an operator:

```json
{\"label\": \"Customer must pass KYC\", \"value\": true}
```

For schema-driven UIs, declare variables on a `BaseVariables` subclass:

```python
from business_rules_genai import BaseVariables, numeric_rule_variable, string_rule_variable


class CustomerVariables(BaseVariables):
    def __init__(self, customer):
        self.customer = customer

    @string_rule_variable(label=\"Customer Segment\", options=[\"SME\", \"ENT\"])
    def segment(self):
        return self.customer[\"segment\"]

    @numeric_rule_variable(description=\"Annual revenue in USD\")
    def revenue(self):
        return self.customer[\"revenue\"]
```

### Functions and expressions

- `function`: call an action before applying an operator.
- `expression`: describe simple math (`+`, `-`, `*`, `/`). Expressions are transpiled into nested action calls so you can reuse the same arithmetic implementations as rule actions.
- `params`: may be a positional list or a named object. Named params are easier to generate from a frontend.
- `{\"var\": \"name\"}`: explicitly reference a variable inside action params or comparison values.
- `{\"literal\": ...}`: force a literal value when a frontend needs to send structured JSON.

```json
{
  \"function\": \"percentage\",
  \"params\": {\"numerator\": {\"var\": \"revenue\"}, \"denominator\": 200},
  \"operator\": \"less_than_or_equal_to\",
  \"value\": 30
}
```

```json
{
  \"expression\": \"(cash / liabilities) * 100\",
  \"operator\": \"greater_than\",
  \"value\": 45
}
```

### Conditional values

`value_condition` lets you derive the comparison value dynamically. Each branch contains a nested rule and either a literal `value` or a list of `actions` to execute.

```json
{
  \"name\": \"margin\",
  \"operator\": \"greater_than_or_equal_to\",
  \"value_condition\": [
    {
      \"conditions\": {\"all\": [{\"name\": \"segment\", \"operator\": \"equal_to\", \"value\": \"SME\"}]},
      \"value\": 10
    },
    {
      \"conditions\": {\"all\": [{\"function\": \"always_true\", \"operator\": \"is_true\"}]},
      \"actions\": [{\"function\": \"set_value_numeric\", \"params\": 5}]
    }
  ]
}
```

The first matching branch wins. If none matches a `RuntimeError` is raised.

### Tracing output

`check_conditions_recursively` and `run_all` return a trace that records each decision:

```json
{
  \"type\": \"all\",
  \"result\": true,
  \"children\": [
    {
      \"type\": \"condition\",
      \"summary\": \"revenue > 100\",
      \"result\": true,
      \"input\": 125,
      \"value\": 100
    }
  ]
}
```

The structure is suitable for powering UIs or audit logs.

### Front-end schema

Use `export_rule_schema` to expose variables, actions, operators, and supported reference shapes to a frontend builder:

```python
from business_rules_genai import BaseActions, export_rule_schema, rule_action


class CustomerActions(BaseActions):
    @rule_action(params={\"value\": \"string\"}, return_type=\"string\")
    def tag(self, value):
        return self.set_value_string(value)


schema = export_rule_schema(CustomerVariables, CustomerActions())
```

The returned dictionary includes:

- `variables`: labels, field types, options, and valid operators.
- `actions`: parameter metadata inferred from decorators and type hints.
- `operators`: catalogued per field type.
- `references`: the explicit JSON shapes for variable and literal references.

## Operators

Operator wrappers expose comparison helpers while keeping values strongly typed. See `business_rules_genai/operators.py` for the full catalogue. Highlights:

- `StringType`: equality, containment, regex, membership checks.
- `NumericType`: numeric comparisons, range checks, tolerance-aware equality.
- `BooleanType`: `is_true` / `is_false`.

## Testing

Run the test suite with:

```bash
pytest
```

## License

MIT
