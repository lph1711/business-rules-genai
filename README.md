business-rules-genai
==============

# Usage

## 1. Define Your set of variables

You define all the available variables for a certain kind of object in your code, and then later dynamically set the conditions and thresholds for those.

Each variable must be defined with correct data types, since each data type will have its own set of operators. Current supported data types (and theirs operators) are:

**numeric** - an integer, float, or python Decimal.

`@numeric_rule_variable` operators:

* `equal_to`
* `greater_than`
* `less_than`
* `greater_than_or_equal_to`
* `less_than_or_equal_to`

**string** - a python bytestring or unicode string.

`@string_rule_variable` operators:

* `equal_to`
* `starts_with`
* `ends_with`
* `contains`
* `matches_regex`
* `non_empty`

**boolean** - a True or False value.

`@boolean_rule_variable` operators:

* `is_true`
* `is_false`

For example:

```python
class CompanyVariables(BaseVariables):

    def __init__(self, company):
        self.company = company

    @string_rule_variable
    def customer_segment(self):
        return self.company.customerSegment
    
    @numeric_rule_variable
    def doanhthu(self):
        return self.company.customerRevenue
    
    @numeric_rule_variable
    def vonchusohuu(self):
        return self.company.vonchusohuu
      
    @boolean_rule_variable
    def engagedInImportsExports(self):
        return self.company['engagedInImportsExports'] == "x"
```

## 2. Define your set of functions

These are the functions that are available to be used when a function is called or a condition is triggered.

A defined function must return a NumericType or StringType

For example:

```python
class CompanyActions(BaseActions):

    def __init__(self, company):
        self.company = company

    def percentage(self, value1, value2):
        if isinstance(value1, NumericType):
            value1 = value1.value
        if isinstance(value2, NumericType):
            value2 = value2.value

        if value2 == 0:
            return NumericType(0)
        return NumericType(round((value1 / value2) * 100))

    def add(self, value1, value2):
        if isinstance(value1, NumericType):
            value1 = value1.value
        if isinstance(value2, NumericType):
            value2 = value2.value
        return NumericType(value1 - value2)
```

## 3. Build the rules

A rule is just a JSON object that gets interpreted by the business-rules-genai engine.

### Variable
A variable of a condition can set in three different methods:

1. Defined variables

```python
{ 
  "name": "vonchusohuu",
  "operator": "greater_than_or_equal_to",
  "value": 5000000000,
}
```

- "name": the name of the defined variable in CompanyVariables class
- "operator": the comparing operator
- "value": value to compared to

2. Function calling
```python
{ 
  "function": "percentage",
  "variable_params": ["doanhthu", 5000000],
  "operator": "less_than_or_equal_to",
  "value": 30
}
```

- "function": the name of the defined function in CompanyActions class
- "variable_params": a list of parameter for the function. A parameter can be a defined variable from CompanyVariables class or a specific value
- "operator": the comparing operator
- "value": value to compared to

3. Math expression
```python
{ 
  "expression": "(vonchusohuu / doanhthu) * 100",
  "operator": "less_than_or_equal_to",
  "value": 45,
}
```

- "expression": the mathematical expression (4 basic operators are supported: +, -, x, /)
- "operator": the comparing operator
- "value": value to compared to

### Condition value

A value in a condition can also be set using a list of sub-conditions. Conditions inside the list will be evaluated top-down, and will stop after the first trigger. Then the value will be set using the action "set_value_numeric" or "set_value"string" according to the data type. For example:
```python
{ 
  "name": "vonchusohuu",
  "operator": "less_than_or_equal_to",
  "value": [
      { "conditions": { "all": [
          { "name": "customer_segment",
            "operator": "equal_to",
            "value": "SME",
          }
      ]},
        "actions": [
            { "name": "set_value_numeric",
              "params": [50]
            }]},

      { "conditions": { "all": [
          { "name": "customer_segment",
            "operator": "equal_to",
            "value": "MMLC",
          }
      ]},
        "actions": [
            { "name": "set_value_numeric",
              "params": [30]
            }]}            
  ]
}
```
### ALL, ANY

An example of the resulting JSON is:

```python
rules = [
{ 
  "conditions": {
     "all": [
      { "name": "vonchusohuu",
        "operator": "greater_than_or_equal_to",
        "value": 5000000000,
      },
      { "function": "percentage",
        "variable_params": ["doanhthu", 200],
        "operator": "less_than_or_equal_to",
        "value": [
            { "conditions": { "all": [
                { "name": "customer_segment",
                  "operator": "equal_to",
                  "value": "SME",
                }
            ]},
              "actions": [
                  { "name": "set_value_numeric",
                    "params": [30]
                  }]},

            { "conditions": { "all": [
                { "name": "customer_segment",
                  "operator": "equal_to",
                  "value": "MMLC",
                }
            ]},
              "actions": [
                  { "name": "set_value_numeric",
                    "params": [0]
                  }]}            
        ]
      },
      { "expression": "(vonchusohuu / doanhthu) * 100",
        "operator": "less_than_or_equal_to",
        "value": "doanhthu",
      }
      ]
    },
  
  "actions": [],
}
]
```

## Run your rules

```python
from business_rules import run_all

rules = _some_function_to_extract_rule_set()

for product in Products.objects.all():
    run_all(rule_list=rules,
            defined_variables=ProductVariables(product),
            defined_actions=ProductActions(product),
            stop_on_first_trigger=True
           )
```
