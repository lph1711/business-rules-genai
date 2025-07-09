from .fields import FIELD_NO_INPUT, FIELD_LIST
from business_rules_genai.operators import NumericType, BooleanType, BaseType, StringType, COMPARISON_OPERATOR_MAP
import ast
import logging
import inspect
from decimal import Decimal

logger = logging.getLogger(__name__)
def run_all(rule_list,
            defined_variables,
            defined_actions,
            stop_on_first_trigger=False,
            return_action_results=False):
    results = []
    rule_was_triggered = False
    for rule in rule_list:
        passed, detailed_results = run(rule, defined_variables, defined_actions, return_action_results)
        if return_action_results and passed:
            return detailed_results
        results += detailed_results
        if passed:
            rule_was_triggered = True
            if stop_on_first_trigger:
                return True, results
    return rule_was_triggered, results 

def run(rule, defined_variables, defined_actions, return_action_results=False):
    conditions, actions = rule.get('conditions', {}), rule.get('actions', {})
    rule_triggered, results = check_conditions_recursively(conditions, defined_variables, defined_actions)
    if rule_triggered:
        action_result = do_actions(actions, defined_variables, defined_actions)
        if return_action_results:
            return True, action_result
        return True, results
    return False, results

def check_conditions_recursively(conditions, defined_variables, defined_actions):
    results = []

    def _check(conds):
        local_results = []

        for key, value in conds.items():
            if key == 'all':
                assert isinstance(value, list) and len(value) >= 1
                group_results = []
                all_passed = True

                for item in value:
                    result, nested = _check(item)
                    group_results.append(nested)
                    if not result:
                        all_passed = False

                local_results.append({
                    "type": "all",
                    "children": group_results,
                    "result": all_passed
                })
            elif key == 'any':
                assert isinstance(value, list) and len(value) >= 1
                group_results = []
                any_passed = False

                for item in value:
                    result, nested = _check(item)
                    group_results.append(nested)
                    if result:
                        any_passed = True

                local_results.append({
                    "type": "any",
                    "children": group_results,
                    "result": any_passed
                })

            else:
                # This is a base case condition
                result = check_condition(conds, defined_variables, defined_actions)

                label = result.get('label')
                operator = COMPARISON_OPERATOR_MAP[result.get('operator')] if result.get('operator') in COMPARISON_OPERATOR_MAP else result.get('operator')
                value = result.get('value') if value is not None else ""

                if conds.get('function') or conds.get('expression'):
                    input = result.get('function_result')

                elif conds.get('name') and _get_variable_value(defined_variables, conds['name']):
                    input = _get_variable_value(defined_variables, conds['name']).value
    
                elif label and not conds.get('name'):
                    local_results.append({
                        "type": "display",
                        "label": label,
                        "threshold": result.get('threshold')
                    })
                    break

                else:
                    input = None
                    
                local_results.append({
                    "type": "condition",
                    "condition": f"{label} {operator} {value}",
                    "input": input,
                    "result": result.get('condition_result')
                })
                break

        # Aggregate results: if all keys are conditions, we assume all must pass
        overall_result = all(item["result"] if isinstance(item.get("result"), bool) and item.get("type") != 'display' else False for item in local_results)
        return overall_result, local_results

    final_result, results = _check(conditions)
    return final_result, results


def check_condition(condition, defined_variables, defined_actions):
    """ Checks a single rule condition - the condition will be made up of
    variables, values, and the comparison operator. The defined_variables
    object must have a variable defined for any variables in this condition.
    """
    operator = condition.get('operator')
    comparison_value = condition.get('value')
    comparison_value_condition = condition.get('value_condition')
    variable = None
    
    if comparison_value_condition:
        comparison_value = run_all(comparison_value_condition, defined_variables, defined_actions, stop_on_first_trigger=True, return_action_results=True)

    if condition.get('expression'):
        # Parse the expression and execute it
        structured_expression = parse_math_expression(condition['expression'])
        variable = execute_math_expression(structured_expression, defined_variables, defined_actions)
        label = condition.get('label') or condition['expression']
    
    elif condition.get('function'):
        variable = do_actions([{
            'function': condition['function'],
            'params': condition.get('params', {})
        }], defined_variables, defined_actions)

        label = condition.get('label') or f"{condition['function']}({', '.join(f'{param}' for param in condition.get('params', []))})"

    elif condition.get('name'):
        variable = _get_variable_value(defined_variables, condition.get('name'))
        label = condition.get('label') or condition.get('name')

    elif condition.get('label'):
        comparison_value = comparison_value.value if isinstance(comparison_value, BaseType) else comparison_value

        return {
            "label": condition.get('label'),
            "threshold": comparison_value
        }
    
    variable_value = variable.value if isinstance(variable, BaseType) else variable
    comparison_value = comparison_value.value if isinstance(comparison_value, BaseType) else comparison_value

    return {"condition_result": _do_operator_comparison(variable, operator, comparison_value),
            "label": label,
            "operator": operator,
            "value": comparison_value,
            "function_result": variable_value}

def _get_variable_value(defined_variables, name):
    """ Call the function provided on the defined_variables object with the
    given name (raise exception if that doesn't exist) and casts it to the
    specified type.

    Returns an instance of operators.BaseType
    """
    def fallback(*args, **kwargs):
        # raise AssertionError("Variable {0} is not defined in class {1}".format(
        #         name, defined_variables.__class__.__name__))
        logger.info(f"Variable {name} is not defined")
        return None
    
    if isinstance(defined_variables, dict):
        val = defined_variables.get(name, None)
    else:
        val = getattr(defined_variables, name, fallback)
    
    if isinstance(val, (int, float, Decimal)):
        return NumericType(val)
    
    elif isinstance(val, bool):
        return BooleanType(val)
    
    elif isinstance(val, str):
        return StringType(val)
    
    else:
        return None

def _do_operator_comparison(operator_type, operator_name, comparison_value):
    """ Finds the method on the given operator_type and compares it to the
    given comparison_value.

    operator_type should be an instance of operators.BaseType
    comparison_value is whatever python type to compare to
    returns a bool
    """

    def fallback(*args, **kwargs):
        raise AssertionError("Operator {0} does not exist for type {1}".format(
            operator_name, operator_type.__class__.__name__))

    if not isinstance(operator_type, BooleanType) and (operator_type is None or operator_type.value is None or comparison_value is None):
        return "N/A"

    method = getattr(operator_type, operator_name, fallback)

    if getattr(method, 'input_type', '') == FIELD_NO_INPUT:
        return method()
    
    if getattr(method, 'comparison_type', '') == FIELD_LIST:
        return method(comparison_value)
    
    if isinstance(comparison_value, list):
        return method(*comparison_value)
    return method(comparison_value)


def do_actions(actions, defined_variables, defined_actions):
    for action in actions:
        method_name = action.get('function') or action.get('name')
        def fallback(*args, **kwargs):
            raise AssertionError("Action {0} is not defined in class {1}"\
                    .format(method_name, defined_actions.__class__.__name__))
        
        params = action.get('params')
        if params is None or params == {}:
            params = []
        elif not isinstance(params, list):
            params = [params]

        print(f"Executing action: {method_name} with params: {params}")
        # Process all parameters for variable substitution
        processed_params = [
            _get_variable_value(defined_variables, param) or param 
            if isinstance(param, str) else param
            for param in params
        ]
        print(f"Processed parameters: {processed_params}")
        method = getattr(defined_actions, method_name, fallback)
        try:
            method_signature = inspect.signature(method)
            if len(method_signature.parameters) != len(processed_params):
                raise AssertionError(f"Action {method_name} expects {len(method_signature.parameters)} parameters, but got {len(processed_params)}.")
            return method(*processed_params)
        except AssertionError:
            raise
        except Exception as e:
            raise RuntimeError(f"'{method_name}': {e}")
            
        

OPERATOR_MAP = {
    ast.Add: "add",
    ast.Sub: "minus",
    ast.Mult: "mult",
    ast.Div: "divide"
}

def parse_math_expression(expression: str):
    """
    Parses a math expression string into a nested dictionary representing
    function calls.
    
    Args:
        expression (str): The mathematical expression string.
    
    Returns:
        tuple: structured_dict)
    """
    tree = ast.parse(expression, mode="eval")

    def parse_node(node):
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            function_name = OPERATOR_MAP.get(op_type)
            if function_name is None:
                raise ValueError(f"Unsupported operator: {op_type}")
            left = parse_node(node.left)
            right = parse_node(node.right)
            return {
                "function": function_name,
                "args": [left, right]
            }
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):  # For numbers like 5, 10.0
            return node.value
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")

    structured = parse_node(tree.body)
    return structured

def execute_math_expression(ast_dict, defined_variables, defined_actions):
    """
    Executes a parsed math expression represented as a nested dictionary.
    
    Args:
        ast_dict (dict): The structured dictionary representing the math expression.
        defined_variables (object): The object containing defined variables.
        defined_actions (object): The object containing defined actions.
    
    Returns:
        float: The result of the evaluated expression.
    """
    if isinstance(ast_dict, dict):
        function_name = ast_dict["function"]
        args = [execute_math_expression(arg, defined_variables, defined_actions) for arg in ast_dict["args"]]
        if None in args:
            return None
        res = do_actions([{
            'function': function_name,
            'params': [args[0], args[1]]
        }], defined_variables, defined_actions)
        return res
    
    elif isinstance(ast_dict, str):
        value = _get_variable_value(defined_variables, ast_dict)
        return value if value.value is not None else None 
    # elif isinstance(ast_dict, (int, float)):
    #     return ast_dict
    else:
        return ast_dict