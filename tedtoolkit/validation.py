'''tedtoolkit.validation - table-shape validation helpers. No intra-package dependencies.'''


def _is_list_of_lists(var, strict_nonempty=False):
    '''return true if list of lists, false if anything else; if strict_nonempty, must be at least
    one row and one column'''
    if isinstance(var, list):
        if strict_nonempty and not var:
            return False
        for line in var:
            if not isinstance(line, list):
                return False
        return True
    else:
        return False


def _check_var_table(var, var_name, strict_nonempty=False):
    '''internal function to ensure that the variable is of type list of lists'''
    if _is_list_of_lists(var, strict_nonempty):
        return
    else:
        raise Exception('Error: Variable {} passed as {} but must be list of lists'.format(
            var_name, str(type(var))))
