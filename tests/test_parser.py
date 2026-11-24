
import pytest

from polylint.languages.python.lexer import Lexer
from polylint.languages.python.parser import Parser, ParserError
from polylint.languages.python import ast_nodes as ast


def parse(source):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def test_empty_module():
    tree = parse("")
    assert isinstance(tree, ast.Module)
    assert tree.body == []


def test_variable_assignment():
    tree = parse("x = 10")
    statement = tree.body[0]

    assert isinstance(statement, ast.Assignment)
    assert statement.targets[0].name == "x"
    assert statement.value.value == 10


def test_binary_expression():
    tree = parse("x = 10 + 20")
    expression = tree.body[0].value

    assert isinstance(expression, ast.BinaryOperation)
    assert expression.operator == "+"


def test_operator_precedence():
    tree = parse("x = 10 + 20 * 3")
    expression = tree.body[0].value

    assert expression.operator == "+"
    assert expression.right.operator == "*"


def test_function_definition():
    tree = parse("def greet(name):\n    print(name)\n")

    function = tree.body[0]

    assert isinstance(function, ast.FunctionDefinition)
    assert function.name == "greet"
    assert function.parameters[0].name == "name"


def test_return_statement():
    tree = parse("def add(a, b):\n    return a + b\n")

    function = tree.body[0]
    statement = function.body[0]

    assert isinstance(statement, ast.ReturnStatement)
    assert isinstance(statement.value, ast.BinaryOperation)


def test_if_statement():
    tree = parse("if x > 10:\n    print(x)\n")

    statement = tree.body[0]

    assert isinstance(statement, ast.IfStatement)
    assert isinstance(statement.test, ast.Comparison)
    assert len(statement.body) == 1


def test_if_else_statement():
    tree = parse(
        "if x > 10:\n"
        "    print('large')\n"
        "else:\n"
        "    print('small')\n"
    )

    statement = tree.body[0]

    assert isinstance(statement, ast.IfStatement)
    assert len(statement.else_body) == 1


def test_while_statement():
    tree = parse("while x < 10:\n    x += 1\n")

    statement = tree.body[0]

    assert isinstance(statement, ast.WhileStatement)
    assert isinstance(statement.body[0], ast.AugmentedAssignment)


def test_for_statement():
    tree = parse("for item in items:\n    print(item)\n")

    statement = tree.body[0]

    assert isinstance(statement, ast.ForStatement)
    assert statement.target.name == "item"


def test_list_expression():
    tree = parse("numbers = [1, 2, 3]")

    expression = tree.body[0].value

    assert isinstance(expression, ast.ListExpression)
    assert len(expression.elements) == 3


def test_function_call():
    tree = parse("result = add(2, 3)")

    expression = tree.body[0].value

    assert isinstance(expression, ast.CallExpression)
    assert len(expression.arguments) == 2


def test_class_definition():
    tree = parse("class Animal:\n    pass\n")

    statement = tree.body[0]

    assert isinstance(statement, ast.ClassDefinition)
    assert statement.name == "Animal"
    assert isinstance(statement.body[0], ast.PassStatement)


def test_import_statement():
    tree = parse("import os")

    assert isinstance(tree.body[0], ast.ImportStatement)
    assert tree.body[0].module == "os"


def test_import_from_statement():
    tree = parse("from math import sqrt")

    statement = tree.body[0]

    assert isinstance(statement, ast.ImportFromStatement)
    assert statement.module == "math"
    assert statement.names[0][0] == "sqrt"


def test_tuple_expression():
    tree = parse("point = (10, 20)")

    expression = tree.body[0].value

    assert isinstance(expression, ast.TupleExpression)
    assert len(expression.elements) == 2


def test_dictionary_expression():
    tree = parse('person = {"name": "Alex"}')

    expression = tree.body[0].value

    assert isinstance(expression, ast.DictionaryExpression)
    assert len(expression.entries) == 1


def test_unary_expression():
    tree = parse("x = -10")

    expression = tree.body[0].value

    assert isinstance(expression, ast.UnaryOperation)
    assert expression.operator == "-"


def test_comparison_expression():
    tree = parse("result = x >= 10")

    expression = tree.body[0].value

    assert isinstance(expression, ast.Comparison)
    assert expression.operators == [">="]


def test_augmented_assignment():
    tree = parse("x += 5")

    statement = tree.body[0]

    assert isinstance(statement, ast.AugmentedAssignment)
    assert statement.operator == "+="


def test_lambda_expression():
    tree = parse("f = lambda x: x + 1")

    expression = tree.body[0].value

    assert isinstance(expression, ast.LambdaExpression)
    assert expression.parameters[0].name == "x"


def test_nested_function():
    tree = parse(
        "def outer():\n"
        "    def inner():\n"
        "        pass\n"
    )

    outer = tree.body[0]

    assert isinstance(outer, ast.FunctionDefinition)
    assert isinstance(outer.body[0], ast.FunctionDefinition)


def test_invalid_syntax():
    with pytest.raises(ParserError):
        parse("x = ")


def test_exception_group_handlers_match_cpython_syntax():
    source = (
        "try:\n"
        "    run()\n"
        "except* (ValueError, TypeError) as errors:\n"
        "    handle(errors)\n"
        "else:\n"
        "    finish()\n"
        "finally:\n"
        "    cleanup()\n"
    )

    compile(source, "<test>", "exec")
    statement = parse(source).body[0]

    assert isinstance(statement, ast.TryStatement)
    assert len(statement.handlers) == 1
    assert statement.handlers[0].is_star is True
    assert isinstance(statement.handlers[0].exception, ast.TupleExpression)
    assert statement.handlers[0].name == "errors"
    assert statement.else_body
    assert statement.finally_body


def test_regular_exception_handler_keeps_legacy_ast_shape():
    source = "try:\n    run()\nexcept ValueError as error:\n    recover(error)\n"
    compile(source, "<test>", "exec")
    handler = parse(source).body[0].handlers[0]

    assert handler.is_star is False
    assert isinstance(handler.exception, ast.Identifier)
    assert handler.exception.name == "ValueError"


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    run()\nexcept*:\n    recover()\n",
        (
            "try:\n"
            "    run()\n"
            "except* ValueError:\n"
            "    recover()\n"
            "except TypeError:\n"
            "    recover()\n"
        ),
        (
            "try:\n"
            "    run()\n"
            "except ValueError:\n"
            "    recover()\n"
            "except* TypeError:\n"
            "    recover()\n"
        ),
    ],
)
def test_invalid_exception_group_handler_forms_match_cpython(source):
    with pytest.raises(SyntaxError):
        compile(source, "<test>", "exec")

    with pytest.raises(ParserError):
        parse(source)
