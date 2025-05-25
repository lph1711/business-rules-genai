from .fields import FIELD_NO_INPUT
import ast

def run_all(rule_list,
            defined_variables,
            defined_actions,
            stop_on_first_trigger=False):
    results = []
    rule_was_triggered = False
    for rule in rule_list:
        passed, detailed_results = run(rule, defined_variables, defined_actions)
        results += detailed_results
        if passed:
            rule_was_triggered = True
            if stop_on_first_trigger:
                return True, results
    return rule_was_triggered, results 

def run(rule, defined_variables, defined_actions):
    conditions, actions = rule['conditions'], rule['actions']
    rule_triggered, results = check_conditions_recursively(conditions, defined_variables, defined_actions)
    if rule_triggered:
        do_actions(actions, defined_variables, defined_actions)
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
                if conds.get('params') or conds.get('expression'):
                    local_results.append({
                        "type": "condition_function",
                        "condition": conds,
                        "input": result['function_result'],
                        "result": result['condition_result']
                        })
                    break
                else:
                    local_results.append({
                        "type": "condition",
                        "condition": conds,
                        "input": _get_variable_value(defined_variables, conds['name']).value,
                        "result": result['condition_result']
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
    if condition.get('expression'):
        # Parse the expression and execute it
        expression, op, value = condition['expression'], condition['operator'], condition['value']
        structured_expression = parse_math_expression(expression)
        result = execute_math_expression(structured_expression, defined_variables, defined_actions)
        return {"condition_result": _do_operator_comparison(result, op, value),
                "function_result": result if result is not None else None}
    elif condition.get('params'):
        func_name, func_params, op, value = condition['function'], condition['params'], condition['operator'], condition['value']
        func_result = do_actions([{
            'function': func_name,
            'params': func_params
        }], defined_variables, defined_actions)
        return {"condition_result" : _do_operator_comparison(func_result, op, value),
                "function_result" : func_result.value if func_result is not None else None}
    else:
        name, op, value = condition['name'], condition['operator'], condition['value']
    operator_type = _get_variable_value(defined_variables, name)
    return {"condition_result": _do_operator_comparison(operator_type, op, value)}

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
        raise AssertionError("Variable {0} is not defined in class {1}".format(
                name, defined_variables.__class__.__name__))
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
    print(operator_type.value, type(operator_type))
    def fallback(*args, **kwargs):
        raise AssertionError("Operator {0} does not exist for type {1}".format(
            operator_name, operator_type.__class__.__name__))
    method = getattr(operator_type, operator_name, fallback)
    if getattr(method, 'input_type', '') == FIELD_NO_INPUT:
        return method()
    return method(comparison_value)


def do_actions(actions, defined_variables, defined_actions):
    for action in actions:
        method_name = action['function']
        def fallback(*args, **kwargs):
            raise AssertionError("Action {0} is not defined in class {1}"\
                    .format(method_name, defined_actions.__class__.__name__))
        params = {}
        if action.get('params'):
            value1 = action['params'].get('value1')
            if isinstance(value1, str):
                value1 = _get_variable_value(defined_variables, value1)

            value2 = action['params'].get('value2')
            if isinstance(value2, str):
                value2 = _get_variable_value(defined_variables, value2)

            params = {'value1': value1, 'value2': value2}

        method = getattr(defined_actions, method_name, fallback)
        return method(**params)

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
            'params': {'value1': args[0], 'value2': args[1]}
        }], defined_variables, defined_actions)

        return res
    elif isinstance(ast_dict, str):
        return _get_variable_value(defined_variables, ast_dict)
    # elif isinstance(ast_dict, (int, float)):
    #     return ast_dict
    else:
        return ast_dict