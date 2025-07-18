business-rules-genai
==============

# Usage

## 1. Define Your set of variables

You define the object that has all the variables, and then later dynamically set the conditions and thresholds for those.

Each data type will have its own set of operators. Current supported data types (and theirs operators) are:

**numeric** - an integer, float, or python Decimal.

`@numeric_rule_variable` operators:

* `equal_to`
* `greater_than`
* `less_than`
* `greater_than_or_equal_to`
* `less_than_or_equal_to`
* `between`
* `between_equal`

**string** - a python bytestring or unicode string.

`@string_rule_variable` operators:

* `equal_to`
* `starts_with`
* `ends_with`
* `contains`
* `matches_regex`
* `non_empty`
* `is_in`

**boolean** - a True or False value.

`@boolean_rule_variable` operators:

* `is_true`
* `is_false`

For example:

```python
class CompanyDetails():
  has_chbh_hdbh: Optional[bool] = None
  tienvatuongduongtien: Optional[Tuple[Any, Any]] = None
  sum_duno_vnd: Optional[int] = None
  sum_duno_usd: Optional[int] = None
  sum_duno_other: Optional[int] = None

# OR

companyDetails = {
  'tax_code': 0,
  'orgnbr_code': 0,
  'max_nhom_no': "01",
  
  'ownersEquity': 50,
  'customerRevenue': 100,
}
```

## 2. Define your set of functions

These are the functions that are available to be used when a function is called or a condition is triggered.

A defined function must return a NumericType or StringType or BooleanType

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
# vonchusohuu >= 5000000000
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
# percentage(doanhthu, 5000000) <= 30
{ 
  "function": "percentage",
  "params": ["doanhthu", 5000000],
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
# (vonchusohuu / doanhthu) * 100 <= 45
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

A value in a condition can also be set using a list of sub-conditions, using **"value_condition"**. Conditions inside the list will be evaluated top-down, and will stop after the first trigger. Then the value will be set using the action "set_value_numeric" or "set_value"string" according to the data type. For example:
```python
{ 
  "name": "vonchusohuu",
  "operator": "less_than_or_equal_to",
  "value_condition": [
      # If customer_segment == "SME" => value = 0
      { "conditions": { "all": [
          { "name": "customer_segment",
            "operator": "equal_to",
            "value": "SME",
          }
      ]},
        "actions": [
            { "name": "set_value_numeric", # Function to set the value
              "params": 0
            }]},

      # Elif customer_segment == "MMLC" => value = 30
      { "conditions": { "all": [
          { "name": "customer_segment",
            "operator": "equal_to",
            "value": "MMLC",
          }
      ]},
        "actions": [
            { "name": "set_value_numeric", # Function to set the value
              "params": 30
            }]},

      # Else => value = 50
      { "conditions": { "all": [  # Always True condition
          { "function": "always_true", # This function will always return True
            "operator": "is_true"
          }
      ]},
        "actions": [
            { "name": "set_value_numeric", # Function to set the value
              "params": 50
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
        "params": ["doanhthu", 200],
        "operator": "less_than_or_equal_to",
        "value_condition": [
          #First condition
            { "conditions": { "all": [
                { "name": "customer_segment",
                  "operator": "equal_to",
                  "value": "SME",
                }
            ]},
              "actions": [
                  { "name": "set_value_numeric",
                    "params": 0
                  }]},

          #Second condition
            { "conditions": { "any": [
                { "name": "customer_segment",
                  "operator": "equal_to",
                  "value": "MMLC",
                },
                { "name": "customer_segment",
                  "operator": "equal_to",
                  "value": "UE",
                }
            ]},
              "actions": [
                  { "name": "set_value_numeric",
                    "params": 30
                  }]},

          #Else condition
            { "conditions": { "all": [
                { "function": "always_true",
                  "operator": "is_true"
                }
            ]},
              "actions": [
                  { "name": "set_value_numeric",
                    "params": 50
                  }]}           
        ]
      },
      { "expression": "(vonchusohuu / doanhthu) * 100",
        "operator": "less_than_or_equal_to",
        "value": 50,
      }
      ]
    },
  
  "actions": [],
}
]
```

This translates directly to:

> **vonchusohuu** >= 5000000000
>
> AND
>
> **percentage**(doanhthu, 200) <= [ x ]
>>   if **customer_segment** == "SME" => 0
>> 
>>   elif **customer_segment** == "MMLC" or **customer_segment** == "UE" => 30
>> 
>>   else => 50
>
> AND
>
> (**vonchusohuu** / **doanhthu**) * 100 <= 50

## Run your rules

```python
from business_rules import run_all

companyDetails = CompanyDetails()
rules = _some_function_to_extract_rule_set()

run_all(rule_list=rules,
        defined_variables=companyDetails,
        defined_actions=CompanyActions(companyDetails),
        stop_on_first_trigger=True
        )
```
