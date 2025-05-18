from .fields import FIELD_NO_INPUT

def run_all(rule_list,
            defined_variables,
            defined_actions,
            stop_on_first_trigger=False):
    results = []
    rule_was_triggered = False
    for rule in rule_list:
        passed, detailed_results = run(rule, defined_variables, defined_actions)
        if passed:
            rule_was_triggered = True
            results += detailed_results
            if stop_on_first_trigger:
                return True, results
    return rule_was_triggered, results 

def run(rule, defined_variables, defined_actions):
    conditions, actions = rule['conditions'], rule['actions']
    rule_triggered, results = check_conditions_recursively(conditions, defined_variables)
    if rule_triggered:
        do_actions(actions, defined_actions)
        return True, results
    return False, results


def check_conditions_recursively(conditions, defined_variables):
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
                result = check_condition(conds, defined_variables)
                local_results.append({
                    "type": "condition",
                    "condition": conds,
                    "input": _get_variable_value(defined_variables, conds['name']).value,
                    "result": result
                })
                break

        # Aggregate results: if all keys are conditions, we assume all must pass
        overall_result = all(item["result"] for item in local_results)
        return overall_result, local_results

    final_result, results = _check(conditions)
    return final_result, results


def check_condition(condition, defined_variables):
    """ Checks a single rule condition - the condition will be made up of
    variables, values, and the comparison operator. The defined_variables
    object must have a variable defined for any variables in this condition.
    """
    name, op, value = condition['name'], condition['operator'], condition['value']
    operator_type = _get_variable_value(defined_variables, name)
    return _do_operator_comparison(operator_type, op, value)

def _get_variable_value(defined_variables, name):
    """ Call the function provided on the defined_variables object with the
    given name (raise exception if that doesn't exist) and casts it to the
    specified type.

    Returns an instance of operators.BaseType
    """
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
    def fallback(*args, **kwargs):
        raise AssertionError("Operator {0} does not exist for type {1}".format(
            operator_name, operator_type.__class__.__name__))
    method = getattr(operator_type, operator_name, fallback)
    if getattr(method, 'input_type', '') == FIELD_NO_INPUT:
        return method()
    return method(comparison_value)


def do_actions(actions, defined_actions):
    for action in actions:
        method_name = action['name']
        def fallback(*args, **kwargs):
            raise AssertionError("Action {0} is not defined in class {1}"\
                    .format(method_name, defined_actions.__class__.__name__))
        params = action.get('params') or {}
        method = getattr(defined_actions, method_name, fallback)
        method(**params)
