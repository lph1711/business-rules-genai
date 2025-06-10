from .fields import FIELD_NO_INPUT
from business_rules_genai.operators import NumericType, BaseType, COMPARISON_OPERATOR_MAP
import ast
import logging
import inspect

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
        if return_action_results:
            return passed
        results += detailed_results
        if passed:
            rule_was_triggered = True
            if stop_on_first_trigger:
                return True, results
    return rule_was_triggered, results 

def run(rule, defined_variables, defined_actions, return_action_results=False):
    conditions, actions = rule['conditions'], rule['actions']
    rule_triggered, results = check_conditions_recursively(conditions, defined_variables, defined_actions)
    if rule_triggered:
        action_result = do_actions(actions, defined_variables, defined_actions)
        if return_action_results:
            return action_result, []
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
                operator = COMPARISON_OPERATOR_MAP[result.get('operator')] if result.get('operator') in COMPARISON_OPERATOR_MAP else result.get('operator')
                local_results.append({
                    "type": "condition",
                    "condition": f"{result.get('label')} {operator} {str(result.get('value'))}",
                    "input": result.get('function_result') if conds.get('function') or conds.get('expression') else _get_variable_value(defined_variables, conds['name']).value,
                    "result": result.get('condition_result')
                })
                break

        # Aggregate results: if all keys are conditions, we assume all must pass
        overall_result = all(item["result"] for item in local_results)
        return overall_result, local_results

    final_result, results = _check(conditions)
    return final_result, results


def check_condition(condition, defined_variables, defined_actions):
    """ Checks a single rule condition - the condition will be made up of
    variables, values, and the comparison operator. The defined_variables
    object must have a variable defined for any variables in this condition.
    """
    operator = condition.get('operator')
    value = condition.get('value')
    variable = None
    
    if isinstance(value, list):
        # If the value is a list, we need to run all the actions in the list
        value = run_all(value, defined_variables, defined_actions, stop_on_first_trigger=True, return_action_results=True)
    # elif isinstance(value, str):
    #     # If the value is a string, we assume it's a variable name
    #     temp_value = _get_variable_value(defined_variables, value)
    #     if temp_value:
    #         value = temp_value
    if condition.get('expression'):
        # Parse the expression and execute it
        structured_expression = parse_math_expression(condition['expression'])
        variable = execute_math_expression(structured_expression, defined_variables, defined_actions)
        label = condition.get('label') or condition['expression']
    
    elif condition.get('function'):
        variable = do_actions([{
            'function': condition['function'],
            'variable_params': condition.get('variable_params', {})
        }], defined_variables, defined_actions)

        label = condition.get('label') or f"{condition['function']}({', '.join(f'{param}' for param in condition.get('variable_params', []))})"
    else:
        variable = _get_variable_value(defined_variables, condition.get('name'))
        label = condition.get('label') or condition.get('name')
    variable_value = variable.value if isinstance(variable, BaseType) else variable

    return {"condition_result": _do_operator_comparison(variable, operator, value),
            "label": label,
            "operator": operator,
            "value": value.value if isinstance(value, BaseType) else value,
            "function_result": variable_value}

def _get_variable_value(defined_variables, name):
    """ Call the function provided on the defined_variables object with the
    given name (raise exception if that doesn't exist) and casts it to the
    specified type.

    Returns an instance of operators.BaseType
    """
    # if type(name) == str:
    #     print(name, type(name))
    # else:
    #     print(name.value, type(name))
    def fallback(*args, **kwargs):
        # raise AssertionError("Variable {0} is not defined in class {1}".format(
        #         name, defined_variables.__class__.__name__))
        logger.info(f"Variable {name} is not defined in class {defined_variables.__class__.__name__}")
        return None
    method = getattr(defined_variables, name, fallback)
    val = method()
    return method.field_type(val)

def _do_operator_comparison(operator_type, operator_name, comparison_value):
    """ Finds the method on the given operator_type and compares it to the
    given comparison_value.

    operator_type should be an instance of operators.BaseType
    comparison_value is whatever python type to compare to
    returns a bool
    """
    # print(operator_type.value, type(operator_type))
    def fallback(*args, **kwargs):
        raise AssertionError("Operator {0} does not exist for type {1}".format(
            operator_name, operator_type.__class__.__name__))
    method = getattr(operator_type, operator_name, fallback)
    if getattr(method, 'input_type', '') == FIELD_NO_INPUT:
        return method()
    return method(comparison_value)


def do_actions(actions, defined_variables, defined_actions):
    for action in actions:
        method_name = action.get('function') or action.get('name')
        def fallback(*args, **kwargs):
            raise AssertionError("Action {0} is not defined in class {1}"\
                    .format(method_name, defined_actions.__class__.__name__))
        params = action.get('variable_params') or action.get('params') or []
        
        # Process all parameters for variable substitution
        processed_params = [
            _get_variable_value(defined_variables, param) or param 
            if isinstance(param, str) else param
            for param in params
        ]
        
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
        res = do_actions([{
            'function': function_name,
            'params': [args[0], args[1]]
        }], defined_variables, defined_actions)
        return res
    
    elif isinstance(ast_dict, str):
        return _get_variable_value(defined_variables, ast_dict)
    # elif isinstance(ast_dict, (int, float)):
    #     return ast_dict
    else:
        return ast_dict