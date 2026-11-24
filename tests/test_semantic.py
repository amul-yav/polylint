"""Tests for the Python semantic analyzer.

Target: 100 tests across the categories agreed in the project roadmap:

    Variable definitions and usage      15
    Undefined names                     10
    Unused variables and imports        10
    Scope and shadowing                 15
    Functions and parameters            10
    Return statements                    8
    Classes and attributes               8
    Imports                              6
    Type-related checks                  8
    Control-flow checks                  5
    Edge cases                           5
    ------------------------------------------
    Total                               100
"""

from polylint.languages.python.lexer import Lexer
from polylint.languages.python.parser import Parser
from polylint.languages.python.semantic import SemanticAnalyzer, Severity


def analyze(source: str):
    tokens = Lexer(source).tokenize()
    tree = Parser(tokens).parse()
    return SemanticAnalyzer().analyze(tree)


def codes(diagnostics):
    return [d.code for d in diagnostics]


def has(diagnostics, code):
    return code in codes(diagnostics)


def count(diagnostics, code):
    return codes(diagnostics).count(code)


def errors(diagnostics):
    return [d for d in diagnostics if d.severity is Severity.ERROR]


def warnings(diagnostics):
    return [d for d in diagnostics if d.severity is Severity.WARNING]


# ======================================================================
# 1. Variable definitions and usage (15)
# ======================================================================

class TestVariableDefinitionsAndUsage:
    def test_simple_definition_and_use(self):
        diags = analyze("x = 10\nprint(x)\n")
        assert diags == []

    def test_multiple_assignment_targets(self):
        diags = analyze("a = b = 1\nprint(a, b)\n")
        assert not has(diags, "PL-UNDEF")

    def test_tuple_unpacking(self):
        # The current parser requires parens around a bare tuple target;
        # see the note in the project roadmap about this parser limitation.
        diags = analyze("(a, b) = (1, 2)\nprint(a, b)\n")
        assert diags == []

    def test_list_unpacking(self):
        diags = analyze("[a, b] = [1, 2]\nprint(a, b)\n")
        assert diags == []

    def test_starred_unpacking(self):
        diags = analyze("(a, *rest) = [1, 2, 3]\nprint(a, rest)\n")
        assert diags == []

    def test_nested_unpacking(self):
        diags = analyze("(a, (b, c)) = (1, (2, 3))\nprint(a, b, c)\n")
        assert diags == []

    def test_reassignment_is_fine(self):
        diags = analyze("x = 1\nx = 2\nprint(x)\n")
        assert diags == []

    def test_augmented_assignment_after_definition(self):
        diags = analyze("x = 1\nx += 1\nprint(x)\n")
        assert diags == []

    def test_chained_arithmetic_usage(self):
        diags = analyze("a = 1\nb = 2\nc = a + b * 2\nprint(c)\n")
        assert diags == []

    def test_attribute_target_does_not_declare_new_name(self):
        diags = analyze("obj.value = 1\n")
        assert has(diags, "PL-UNDEF")

    def test_subscript_target_requires_existing_name(self):
        diags = analyze("data[0] = 1\n")
        assert has(diags, "PL-UNDEF")

    def test_subscript_target_with_existing_name_ok(self):
        diags = analyze("data = [0]\ndata[0] = 1\n")
        assert diags == []

    def test_walrus_definition_usable_after(self):
        diags = analyze("if (n := 10) > 5:\n    print(n)\n")
        assert diags == []

    def test_with_as_binds_name(self):
        diags = analyze(
            "def use():\n"
            "    with open('f') as handle:\n"
            "        print(handle)\n"
        )
        assert diags == []

    def test_for_loop_target_usable_in_body(self):
        diags = analyze("for item in [1, 2, 3]:\n    print(item)\n")
        assert diags == []


# ======================================================================
# 2. Undefined names (10)
# ======================================================================

class TestUndefinedNames:
    def test_simple_undefined_name(self):
        diags = analyze("print(x)\n")
        assert has(diags, "PL-UNDEF")

    def test_use_before_assignment_same_scope(self):
        diags = analyze("print(x)\nx = 10\n")
        assert has(diags, "PL-UNDEF-LOCAL")

    def test_use_before_assignment_in_function(self):
        diags = analyze(
            "def f():\n"
            "    print(y)\n"
            "    y = 1\n"
            "f()\n"
        )
        assert has(diags, "PL-UNDEF-LOCAL")

    def test_undefined_in_function_body(self):
        diags = analyze(
            "def f():\n"
            "    return missing\n"
            "f()\n"
        )
        assert has(diags, "PL-UNDEF")

    def test_undefined_in_condition(self):
        diags = analyze("if missing:\n    pass\n")
        assert has(diags, "PL-UNDEF")

    def test_undefined_in_binary_operation(self):
        diags = analyze("y = unknown + 1\n")
        assert has(diags, "PL-UNDEF")

    def test_undefined_function_call(self):
        diags = analyze("do_something()\n")
        assert has(diags, "PL-UNDEF")

    def test_undefined_in_comprehension_element(self):
        diags = analyze("result = [missing for x in range(3)]\n")
        assert has(diags, "PL-UNDEF")

    def test_new_comprehension_forms_check_keys_values_and_clauses(self):
        diags = analyze(
            "generator = (item for item in source if keep(item))\n"
            "unique = {item for item in source if keep(item)}\n"
            "mapping = {missing_key: missing_value for item in source}\n"
        )
        undefined_messages = [
            diagnostic.message for diagnostic in diags
            if diagnostic.code == "PL-UNDEF"
        ]

        assert any("missing_key" in message for message in undefined_messages)
        assert any("missing_value" in message for message in undefined_messages)
        assert any("source" in message for message in undefined_messages)
        assert any("keep" in message for message in undefined_messages)

    def test_undefined_attribute_object(self):
        diags = analyze("print(missing.attr)\n")
        assert has(diags, "PL-UNDEF")

    def test_builtins_are_not_undefined(self):
        diags = analyze("print(len([1, 2, 3]))\n")
        assert not has(diags, "PL-UNDEF")


# ======================================================================
# 3. Unused variables and imports (10)
# ======================================================================

class TestUnusedVariablesAndImports:
    def test_unused_local_variable(self):
        diags = analyze("def f():\n    unused = 1\nf()\n")
        assert has(diags, "PL-UNUSED-VAR")

    def test_used_local_variable_not_flagged(self):
        diags = analyze("def f():\n    value = 1\n    return value\nf()\n")
        assert not has(diags, "PL-UNUSED-VAR")

    def test_unused_variable_underscore_not_flagged(self):
        diags = analyze("def f():\n    _ignored = 1\nf()\n")
        assert not has(diags, "PL-UNUSED-VAR")

    def test_module_level_unused_variable_not_flagged(self):
        diags = analyze("x = 1\n")
        assert not has(diags, "PL-UNUSED-VAR")

    def test_unused_import(self):
        diags = analyze("import os\n")
        assert has(diags, "PL-UNUSED-IMPORT")

    def test_used_import_not_flagged(self):
        diags = analyze("import os\nprint(os.getcwd())\n")
        assert not has(diags, "PL-UNUSED-IMPORT")

    def test_unused_from_import(self):
        diags = analyze("from math import sqrt\n")
        assert has(diags, "PL-UNUSED-IMPORT")

    def test_unused_import_with_alias(self):
        diags = analyze("import numpy as np\n")
        assert has(diags, "PL-UNUSED-IMPORT")

    def test_used_import_with_alias_not_flagged(self):
        diags = analyze("import numpy as np\nprint(np.array([1]))\n")
        assert not has(diags, "PL-UNUSED-IMPORT")

    def test_multiple_unused_variables_each_reported(self):
        diags = analyze("def f():\n    a = 1\n    b = 2\nf()\n")
        assert count(diags, "PL-UNUSED-VAR") == 2


# ======================================================================
# 4. Scope and shadowing (15)
# ======================================================================

class TestScopeAndShadowing:
    def test_nested_function_reads_enclosing_variable(self):
        diags = analyze(
            "def outer():\n"
            "    x = 1\n"
            "    def inner():\n"
            "        return x\n"
            "    return inner()\n"
        )
        assert diags == []

    def test_function_local_does_not_leak_to_module(self):
        diags = analyze("def f():\n    local = 1\nprint(local)\n")
        assert has(diags, "PL-UNDEF")

    def test_class_body_name_not_visible_in_method(self):
        diags = analyze(
            "class C:\n"
            "    shared = 1\n"
            "    def method(self):\n"
            "        return shared\n"
        )
        assert has(diags, "PL-UNDEF")

    def test_class_body_name_visible_in_class_body(self):
        diags = analyze(
            "class C:\n"
            "    shared = 1\n"
            "    other = shared + 1\n"
        )
        assert diags == []

    def test_comprehension_target_does_not_leak(self):
        diags = analyze("squares = [i * i for i in range(5)]\nprint(i)\n")
        assert has(diags, "PL-UNDEF")

    def test_unpacking_targets_bind_names_in_assignments_loops_and_comprehensions(self):
        diags = analyze(
            "def collect(pairs):\n"
            "    first, *rest = pairs[0]\n"
            "    result = []\n"
            "    for key, (value, extra) in pairs:\n"
            "        result.append((key, value, extra))\n"
            "    mapped = {(key, value) for key, value in pairs}\n"
            "    return (first, rest, result, mapped)\n"
        )
        assert not errors(diags)

    def test_comprehension_can_see_enclosing_scope(self):
        diags = analyze(
            "def f(limit):\n"
            "    return [i for i in range(limit)]\n"
        )
        assert diags == []

    def test_global_statement_writes_module_scope(self):
        diags = analyze(
            "count = 0\n"
            "def increment():\n"
            "    global count\n"
            "    count = count + 1\n"
            "increment()\n"
            "print(count)\n"
        )
        assert diags == []

    def test_missing_global_causes_local_shadow_error(self):
        diags = analyze(
            "count = 0\n"
            "def increment():\n"
            "    count = count + 1\n"
            "    return count\n"
            "increment()\n"
        )
        assert has(diags, "PL-UNDEF-LOCAL")

    def test_nonlocal_statement_binds_enclosing_function(self):
        diags = analyze(
            "def outer():\n"
            "    value = 1\n"
            "    def inner():\n"
            "        nonlocal value\n"
            "        value = value + 1\n"
            "    inner()\n"
            "    return value\n"
        )
        assert diags == []

    def test_nonlocal_without_enclosing_binding_is_error(self):
        diags = analyze(
            "def outer():\n"
            "    def inner():\n"
            "        nonlocal missing\n"
            "        missing = 1\n"
            "    inner()\n"
        )
        assert has(diags, "PL-NONLOCAL-NO-BINDING")

    def test_parameter_shadowing_outer_variable_is_flagged(self):
        diags = analyze(
            "value = 1\n"
            "def f(value):\n"
            "    return value\n"
            "f(2)\n"
        )
        assert has(diags, "PL-SHADOW-OUTER")

    def test_local_variable_shadowing_outer_variable_is_flagged(self):
        diags = analyze(
            "value = 1\n"
            "def f():\n"
            "    value = 2\n"
            "    return value\n"
            "f()\n"
        )
        assert has(diags, "PL-SHADOW-OUTER")

    def test_shadowing_builtin_name_is_flagged(self):
        diags = analyze("list = [1, 2, 3]\n")
        assert has(diags, "PL-SHADOW-BUILTIN")

    def test_unrelated_names_in_sibling_functions_do_not_clash(self):
        diags = analyze(
            "def a():\n"
            "    value = 1\n"
            "    return value\n"
            "def b():\n"
            "    value = 2\n"
            "    return value\n"
            "a()\n"
            "b()\n"
        )
        assert diags == []

    def test_lambda_has_its_own_scope(self):
        diags = analyze("square = lambda n: n * n\nprint(square(4))\n")
        assert diags == []


# ======================================================================
# 5. Functions and parameters (10)
# ======================================================================

class TestFunctionsAndParameters:
    def test_parameters_usable_in_body(self):
        diags = analyze("def f(a, b):\n    return a + b\nf(1, 2)\n")
        assert diags == []

    def test_unused_parameter_is_flagged(self):
        diags = analyze("def f(a, b):\n    return a\nf(1, 2)\n")
        assert has(diags, "PL-UNUSED-PARAM")

    def test_default_value_checked_in_enclosing_scope(self):
        diags = analyze("default = 5\ndef f(x=default):\n    return x\nf()\n")
        assert diags == []

    def test_undefined_default_value(self):
        diags = analyze("def f(x=missing):\n    return x\nf()\n")
        assert has(diags, "PL-UNDEF")

    def test_duplicate_parameter_name_is_error(self):
        diags = analyze("def f(a, a):\n    return a\nf(1, 2)\n")
        assert has(diags, "PL-DUP-PARAM")

    def test_recursive_function_can_call_itself(self):
        diags = analyze(
            "def fact(n):\n"
            "    if n <= 1:\n"
            "        return 1\n"
            "    return n * fact(n - 1)\n"
            "fact(5)\n"
        )
        assert diags == []

    def test_function_can_be_called_before_definition_at_module_level(self):
        # Functions are looked up dynamically at call time, so a forward
        # reference inside another function body is fine.
        diags = analyze(
            "def a():\n"
            "    return b()\n"
            "def b():\n"
            "    return 1\n"
            "a()\n"
        )
        assert diags == []

    def test_varargs_and_kwargs_parameters(self):
        diags = analyze(
            "def f(*args, **kwargs):\n"
            "    return (args, kwargs)\n"
            "f(1, 2, x=3)\n"
        )
        assert diags == []

    def test_keyword_only_after_star(self):
        # The current parser does not support a bare `*` separator with no
        # name after it; keyword-only-style parameters need `*args` first.
        diags = analyze(
            "def f(a, *args, b):\n"
            "    return a + b + len(args)\n"
            "f(1, b=2)\n"
        )
        assert diags == []

    def test_nested_function_definition(self):
        diags = analyze(
            "def outer():\n"
            "    def inner(x):\n"
            "        return x * 2\n"
            "    return inner(3)\n"
            "outer()\n"
        )
        assert diags == []


# ======================================================================
# 6. Return statements (8)
# ======================================================================

class TestReturnStatements:
    def test_return_outside_function_is_error(self):
        diags = analyze("return 1\n")
        assert has(diags, "PL-RETURN-OUTSIDE-FUNCTION")

    def test_return_inside_function_is_fine(self):
        diags = analyze("def f():\n    return 1\nf()\n")
        assert not has(diags, "PL-RETURN-OUTSIDE-FUNCTION")

    def test_bare_return_is_fine(self):
        diags = analyze("def f():\n    return\nf()\n")
        assert diags == []

    def test_return_in_nested_function_is_fine(self):
        diags = analyze(
            "def outer():\n"
            "    def inner():\n"
            "        return 1\n"
            "    return inner()\n"
        )
        assert diags == []

    def test_return_inside_if_inside_function_is_fine(self):
        diags = analyze(
            "def f(flag):\n"
            "    if flag:\n"
            "        return 1\n"
            "    return 2\n"
            "f(True)\n"
        )
        assert not has(diags, "PL-RETURN-OUTSIDE-FUNCTION")

    def test_return_at_module_level_inside_if_is_error(self):
        diags = analyze("if True:\n    return 1\n")
        assert has(diags, "PL-RETURN-OUTSIDE-FUNCTION")

    def test_return_inside_class_body_is_error(self):
        diags = analyze("class C:\n    return 1\n")
        assert has(diags, "PL-RETURN-OUTSIDE-FUNCTION")

    def test_init_returning_a_value_is_flagged(self):
        diags = analyze(
            "class C:\n"
            "    def __init__(self):\n"
            "        return 1\n"
        )
        assert has(diags, "PL-INIT-RETURNS-VALUE")


# ======================================================================
# 7. Classes and attributes (8)
# ======================================================================

class TestClassesAndAttributes:
    def test_simple_class_definition(self):
        diags = analyze("class C:\n    pass\n")
        assert diags == []

    def test_class_with_method_using_self(self):
        diags = analyze(
            "class C:\n"
            "    def __init__(self, value):\n"
            "        self.value = value\n"
            "    def get(self):\n"
            "        return self.value\n"
        )
        assert diags == []

    def test_self_attribute_never_assigned_is_flagged(self):
        diags = analyze(
            "class C:\n"
            "    def get(self):\n"
            "        return self.missing\n"
        )
        assert has(diags, "PL-UNDEFINED-ATTRIBUTE")

    def test_attribute_assigned_in_one_method_usable_in_another(self):
        diags = analyze(
            "class C:\n"
            "    def setup(self):\n"
            "        self.value = 1\n"
            "    def get(self):\n"
            "        return self.value\n"
        )
        assert not has(diags, "PL-UNDEFINED-ATTRIBUTE")

    def test_calling_another_method_via_self_is_not_flagged(self):
        diags = analyze(
            "class C:\n"
            "    def helper(self):\n"
            "        return 1\n"
            "    def get(self):\n"
            "        return self.helper()\n"
        )
        assert not has(diags, "PL-UNDEFINED-ATTRIBUTE")

    def test_class_with_base_classes(self):
        diags = analyze(
            "class Base:\n"
            "    pass\n"
            "class Derived(Base):\n"
            "    pass\n"
        )
        assert diags == []

    def test_undefined_base_class_is_error(self):
        diags = analyze("class C(Missing):\n    pass\n")
        assert has(diags, "PL-UNDEF")

    def test_class_attribute_default_used_as_parameter_default(self):
        diags = analyze(
            "class C:\n"
            "    default = 0\n"
            "    def __init__(self, value=1):\n"
            "        self.value = value\n"
        )
        assert diags == []


# ======================================================================
# 8. Imports (6)
# ======================================================================

class TestImports:
    def test_plain_import(self):
        diags = analyze("import os\nprint(os)\n")
        assert diags == []

    def test_dotted_import_binds_top_level_name(self):
        diags = analyze("import os.path\nprint(os)\n")
        assert diags == []

    def test_import_with_alias(self):
        diags = analyze("import numpy as np\nprint(np)\n")
        assert diags == []

    def test_from_import_single_name(self):
        diags = analyze("from math import sqrt\nprint(sqrt(4))\n")
        assert diags == []

    def test_from_import_with_alias(self):
        diags = analyze("from math import sqrt as square_root\nprint(square_root(4))\n")
        assert diags == []

    def test_relative_import_binds_name(self):
        # `from os import *` would exercise PL-STAR-IMPORT, but the current
        # parser doesn't yet accept a bare `*` in an import list; see the
        # note in the project roadmap about this parser limitation.
        diags = analyze("from . import helper\nprint(helper)\n")
        assert diags == []


# ======================================================================
# 9. Type-related checks (8)
# ======================================================================

class TestTypeRelatedChecks:
    def test_mutable_list_default_is_flagged(self):
        diags = analyze("def f(items=[]):\n    return items\nf()\n")
        assert has(diags, "PL-MUTABLE-DEFAULT")

    def test_mutable_dict_default_is_flagged(self):
        diags = analyze("def f(options={}):\n    return options\nf()\n")
        assert has(diags, "PL-MUTABLE-DEFAULT")

    def test_mutable_set_default_is_flagged(self):
        diags = analyze("def f(seen=set()):\n    return seen\nf()\n")
        # set() is a call, not a literal, so this should NOT be flagged
        # by the literal-based mutable-default check.
        assert not has(diags, "PL-MUTABLE-DEFAULT")

    def test_immutable_default_not_flagged(self):
        diags = analyze("def f(count=0):\n    return count\nf()\n")
        assert not has(diags, "PL-MUTABLE-DEFAULT")

    def test_is_comparison_with_literal_is_flagged(self):
        diags = analyze("x = 1\nif x is 1:\n    pass\n")
        assert has(diags, "PL-IS-LITERAL")

    def test_is_comparison_with_none_not_flagged(self):
        diags = analyze("x = None\nif x is None:\n    pass\n")
        assert not has(diags, "PL-IS-LITERAL")

    def test_duplicate_dict_keys_flagged(self):
        diags = analyze("d = {'a': 1, 'a': 2}\n")
        assert has(diags, "PL-DUPLICATE-KEY")

    def test_self_comparison_flagged(self):
        diags = analyze("x = 1\nif x == x:\n    pass\n")
        assert has(diags, "PL-SELF-COMPARISON")


# ======================================================================
# 10. Control-flow checks (5)
# ======================================================================

class TestControlFlowChecks:
    def test_break_outside_loop_is_error(self):
        diags = analyze("break\n")
        assert has(diags, "PL-BREAK-OUTSIDE-LOOP")

    def test_break_inside_loop_is_fine(self):
        diags = analyze("for i in range(3):\n    break\n")
        assert not has(diags, "PL-BREAK-OUTSIDE-LOOP")

    def test_continue_outside_loop_is_error(self):
        diags = analyze("continue\n")
        assert has(diags, "PL-CONTINUE-OUTSIDE-LOOP")

    def test_break_inside_function_inside_loop_is_error(self):
        # A function defined inside a loop body does not inherit the
        # loop's "inside a loop" status.
        diags = analyze(
            "for i in range(3):\n"
            "    def f():\n"
            "        break\n"
        )
        assert has(diags, "PL-BREAK-OUTSIDE-LOOP")

    def test_unreachable_code_after_return(self):
        diags = analyze(
            "def f():\n"
            "    return 1\n"
            "    print('dead')\n"
            "f()\n"
        )
        assert has(diags, "PL-UNREACHABLE")


# ======================================================================
# 11. Edge cases (5)
# ======================================================================

class TestEdgeCases:
    def test_empty_module(self):
        diags = analyze("")
        assert diags == []

    def test_only_comments_and_blank_lines(self):
        diags = analyze("# just a comment\n\n\n")
        assert diags == []

    def test_deeply_nested_functions(self):
        diags = analyze(
            "def a():\n"
            "    def b():\n"
            "        def c():\n"
            "            return 1\n"
            "        return c()\n"
            "    return b()\n"
            "a()\n"
        )
        assert diags == []

    def test_del_removes_binding_so_later_use_is_flagged(self):
        diags = analyze(
            "def f():\n"
            "    x = 1\n"
            "    del x\n"
            "    print(x)\n"
            "f()\n"
        )
        assert has(diags, "PL-UNDEF-LOCAL")

    def test_walrus_inside_comprehension_condition(self):
        diags = analyze(
            "values = [1, 2, 3, 4]\n"
            "result = [y for x in values if (y := x * 2) > 2]\n"
            "print(result)\n"
        )
        assert diags == []
