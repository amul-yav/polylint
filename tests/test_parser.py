
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


def test_list_comprehension_preserves_existing_ast_shape():
    source = "squares = [x * x for x in values if x > 0]\n"
    compile(source, "<test>", "exec")
    expression = parse(source).body[0].value

    assert isinstance(expression, ast.ListComprehension)
    assert len(expression.generators) == 1
    assert len(expression.generators[0].conditions) == 1


def test_generator_expression():
    source = (
        "squares = (x * x for x in range(10))\n"
        "total = sum(x * x for x in range(10))\n"
    )
    compile(source, "<test>", "exec")
    expression, call = [stmt.value for stmt in parse(source).body]

    assert isinstance(expression, ast.GeneratorExpression)
    assert expression.element.operator == "*"
    assert len(expression.generators) == 1
    assert isinstance(call.arguments[0], ast.GeneratorExpression)


def test_set_and_dictionary_comprehensions():
    source = (
        "unique_squares = {x * x for x in values}\n"
        "square_map = {x: x * x for x in values}\n"
    )
    compile(source, "<test>", "exec")
    set_expression, dict_expression = [stmt.value for stmt in parse(source).body]

    assert isinstance(set_expression, ast.SetComprehension)
    assert isinstance(dict_expression, ast.DictionaryComprehension)
    assert dict_expression.key.name == "x"
    assert dict_expression.element.operator == "*"


def test_comprehensions_with_multiple_clauses_and_filters():
    source = (
        "values = [\n"
        "    (x, y)\n"
        "    for x in rows if x\n"
        "    if keep(x)\n"
        "    for y in columns if y > 0\n"
        "]\n"
        "pairs = {x: y for x in rows for y in columns if valid(x, y)}\n"
    )
    compile(source, "<test>", "exec")
    list_expression, dict_expression = [stmt.value for stmt in parse(source).body]

    assert isinstance(list_expression, ast.ListComprehension)
    assert len(list_expression.generators) == 2
    assert [len(clause.conditions) for clause in list_expression.generators] == [
        2, 1,
    ]
    assert isinstance(dict_expression, ast.DictionaryComprehension)
    assert len(dict_expression.generators) == 2


def test_nested_generator_expression_inside_comprehension():
    source = "nested = [tuple(x for x in row) for row in rows]\n"
    compile(source, "<test>", "exec")
    outer = parse(source).body[0].value

    assert isinstance(outer, ast.ListComprehension)
    assert isinstance(outer.element, ast.CallExpression)
    assert isinstance(outer.element.arguments[0], ast.GeneratorExpression)


def test_async_comprehension_clauses():
    source = (
        "async def collect(streams):\n"
        "    return [item async for stream in streams "
        "for item in stream if item]\n"
    )
    compile(source, "<test>", "exec")
    expression = parse(source).body[0].body[0].value

    assert isinstance(expression, ast.ListComprehension)
    assert expression.generators[0].is_async is True
    assert expression.generators[1].is_async is False


@pytest.mark.parametrize(
    "source",
    [
        "values = [x for x in]\n",
        "values = {x for x in items if}\n",
        "values = {x: for x in items}\n",
        "values = (x for x in items for)\n",
        "values = consume(x for x in items, other)\n",
        "values = consume(x for x in items,)\n",
        "values = consume(value=x for x in items)\n",
        "values = [item async for item in items]\n",
    ],
)
def test_invalid_comprehensions_match_cpython(source):
    with pytest.raises(SyntaxError):
        compile(source, "<test>", "exec")

    with pytest.raises(ParserError):
        parse(source)


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


def test_bare_tuple_and_nested_unpacking_targets():
    source = (
        "key, value = pair\n"
        "first, (second, rest) = values\n"
        "for outer, (inner, *tail) in rows:\n"
        "    consume(outer, inner, tail)\n"
    )
    compile(source, "<test>", "exec")
    tree = parse(source)

    assignment = tree.body[0]
    assert isinstance(assignment, ast.Assignment)
    assert isinstance(assignment.targets[0], ast.TupleExpression)
    nested_assignment = tree.body[1]
    assert isinstance(nested_assignment.targets[0], ast.TupleExpression)
    assert isinstance(nested_assignment.targets[0].elements[1], ast.TupleExpression)

    loop = tree.body[2]
    assert isinstance(loop, ast.ForStatement)
    assert isinstance(loop.target, ast.TupleExpression)
    nested_target = loop.target.elements[1]
    assert isinstance(nested_target, ast.TupleExpression)
    assert isinstance(nested_target.elements[1], ast.StarredExpression)


def test_starred_assignment_and_tuple_rhs():
    source = (
        "first, *rest = values\n"
        "left, right = 1, 2\n"
        "a = b = 3, 4\n"
        "empty, () = values\n"
    )
    compile(source, "<test>", "exec")
    statements = parse(source).body

    assert isinstance(statements[0].targets[0].elements[1], ast.StarredExpression)
    assert isinstance(statements[1].value, ast.TupleExpression)
    assert statements[2].targets[1].name == "b"
    assert isinstance(statements[2].value, ast.TupleExpression)
    assert isinstance(statements[3].targets[0].elements[1], ast.TupleExpression)
    assert statements[3].targets[0].elements[1].elements == []


def test_unpacking_targets_in_comprehensions():
    source = (
        "result = {(key, value) for key, value in pairs}\n"
        "nested = [first for first, (second, *rest) in rows]\n"
    )
    compile(source, "<test>", "exec")
    dictionary_set, list_expression = [stmt.value for stmt in parse(source).body]

    assert isinstance(dictionary_set, ast.SetComprehension)
    assert isinstance(dictionary_set.generators[0].target, ast.TupleExpression)
    assert isinstance(list_expression.generators[0].target, ast.TupleExpression)
    assert isinstance(
        list_expression.generators[0].target.elements[1].elements[1],
        ast.StarredExpression,
    )


@pytest.mark.parametrize(
    "source",
    [
        "*rest = values\n",
        "first, *middle, *rest = values\n",
        "first + second = values\n",
        "for *rest in values:\n    pass\n",
        "for first, *middle, *rest in values:\n    pass\n",
        "result = [item for *rest in values]\n",
    ],
)
def test_invalid_unpacking_targets_match_cpython(source):
    with pytest.raises(SyntaxError):
        compile(source, "<test>", "exec")

    with pytest.raises(ParserError):
        parse(source)


def test_lambda_expression():
    tree = parse("f = lambda x: x + 1")

    expression = tree.body[0].value

    assert isinstance(expression, ast.LambdaExpression)
    assert expression.parameters[0].name == "x"


def test_lambda_parameter_kinds_defaults_and_ordering():
    source = (
        "f = lambda positional, /, normal=2, *args, "
        "required, optional=4, **kwargs: (\n"
        "    positional, normal, args, required, optional, kwargs\n"
        ")\n"
    )
    compile(source, "<test>", "exec")
    parameters = parse(source).body[0].value.parameters

    assert [parameter.name for parameter in parameters] == [
        "positional", "/", "normal", "args", "required", "optional", "kwargs",
    ]
    assert parameters[1].kind == "positional_only"
    assert parameters[2].kind == "normal"
    assert parameters[2].default.value == 2
    assert parameters[3].kind == "varargs"
    assert parameters[4].kind == "keyword_only"
    assert parameters[4].default is None
    assert parameters[5].kind == "keyword_only"
    assert parameters[5].default.value == 4
    assert parameters[6].kind == "kwargs"


def test_lambda_bare_keyword_only_separator():
    source = "f = lambda value, *, required, optional=None: (value, required, optional)\n"
    compile(source, "<test>", "exec")
    parameters = parse(source).body[0].value.parameters

    assert [parameter.kind for parameter in parameters] == [
        "normal", "keyword_only", "keyword_only",
    ]


def test_lambda_default_can_be_a_conditional_expression():
    source = "f = lambda value=1 if enabled else 2: value\n"
    compile(source, "<test>", "exec")
    default = parse(source).body[0].value.parameters[0].default

    assert isinstance(default, ast.ConditionalExpression)


def test_function_parameter_parser_preserves_annotations_and_adds_keyword_only():
    source = (
        "def f(value: int, /, normal: str = 'x', *args: object, "
        "required: bool, optional: int = 3, **kwargs: object) -> int:\n"
        "    return value\n"
    )
    compile(source, "<test>", "exec")
    parameters = parse(source).body[0].parameters

    assert [parameter.name for parameter in parameters] == [
        "value", "/", "normal", "args", "required", "optional", "kwargs",
    ]
    assert parameters[0].annotation.name == "int"
    assert parameters[4].kind == "keyword_only"
    assert parameters[4].annotation.name == "bool"
    assert parameters[6].kind == "kwargs"


@pytest.mark.parametrize(
    "source",
    [
        "f = lambda /, value: value\n",
        "f = lambda value, /, /, other: value\n",
        "f = lambda *args, /: args\n",
        "f = lambda value=1, other: value\n",
        "f = lambda *, **kwargs: kwargs\n",
        "f = lambda **kwargs, value: value\n",
        "f = lambda value, value: value\n",
        "f = lambda *args, *more: args\n",
    ],
)
def test_invalid_lambda_parameter_forms_match_cpython(source):
    with pytest.raises(SyntaxError):
        compile(source, "<test>", "exec")

    with pytest.raises(ParserError):
        parse(source)


@pytest.mark.parametrize(
    "source",
    [
        "def f(value=1, other):\n    pass\n",
        "def f(/, value):\n    pass\n",
        "def f(value, /, /, other):\n    pass\n",
        "def f(*, **kwargs):\n    pass\n",
        "def f(**kwargs, value):\n    pass\n",
        "def f(*args, /):\n    pass\n",
    ],
)
def test_invalid_function_parameter_order_matches_cpython(source):
    with pytest.raises(SyntaxError):
        compile(source, "<test>", "exec")

    with pytest.raises(ParserError):
        parse(source)


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


def test_fstring_literal_text_and_replacement_expressions():
    source = 'message = f"Hello {user.name}, {count + 1}!"\n'
    compile(source, "<test>", "exec")
    expression = parse(source).body[0].value

    assert isinstance(expression, ast.FStringExpression)
    assert [type(part) for part in expression.parts] == [
        ast.FStringText, ast.FStringField, ast.FStringText,
        ast.FStringField, ast.FStringText,
    ]
    assert isinstance(expression.parts[1].expression, ast.AttributeAccess)
    assert isinstance(expression.parts[3].expression, ast.BinaryOperation)


@pytest.mark.parametrize("conversion", ["s", "r", "a"])
def test_fstring_conversion_flags(conversion):
    source = f'value = f"{{value!{conversion}}}"\n'
    compile(source, "<test>", "exec")
    field = parse(source).body[0].value.parts[0]

    assert isinstance(field, ast.FStringField)
    assert field.conversion == conversion


def test_fstring_format_specification_and_nested_fields():
    source = 'formatted = f"{value:{width}.{precision}f}"\n'
    compile(source, "<test>", "exec")
    field = parse(source).body[0].value.parts[0]

    assert isinstance(field, ast.FStringField)
    assert len(field.format_spec) == 4
    assert isinstance(field.format_spec[0], ast.FStringField)
    assert isinstance(field.format_spec[2], ast.FStringField)
    assert field.format_spec[3].value == "f"


def test_fstring_escaped_braces_and_debug_conversion():
    source = 'message = f"{{name}} = {name = !r}"\n'
    compile(source, "<test>", "exec")
    expression = parse(source).body[0].value

    assert expression.parts[0].value == "{name} = "
    assert expression.parts[1].debug_text == "name = "
    assert expression.parts[1].conversion == "r"


def test_fstring_nested_quotes_and_nested_fstring_expression():
    source = 'message = f"outer {f\'{mapping["key"]}\'}"\n'
    compile(source, "<test>", "exec")
    outer_field = parse(source).body[0].value.parts[1]

    assert isinstance(outer_field.expression, ast.FStringExpression)
    inner_field = outer_field.expression.parts[0]
    assert isinstance(inner_field.expression, ast.SubscriptExpression)


def test_raw_and_multiline_fstring_parts():
    source = 'message = rf"""path={path}\\n{name}\n"""\n'
    compile(source, "<test>", "exec")
    expression = parse(source).body[0].value

    assert isinstance(expression, ast.FStringExpression)
    assert expression.parts[0].value == "path="
    assert expression.parts[2].value == "\\n"
    assert expression.parts[-1].value == "\n"


@pytest.mark.parametrize(
    "source",
    [
        'f"literal }"',
        'f"{}"',
        'f"{value!q}"',
        'f"{value"',
        'f"{value:.2f"',
    ],
)
def test_invalid_fstrings_match_cpython(source):
    with pytest.raises(SyntaxError):
        compile(source, "<test>", "eval")

    with pytest.raises((ParserError, SyntaxError)):
        parse(source)


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


def test_parenthesized_with_multiple_context_managers():
    source = (
        "with (\n"
        "    open('input.txt') as source,\n"
        "    open('output.txt', 'w') as destination,\n"
        "):\n"
        "    destination.write(source.read())\n"
    )
    compile(source, "<test>", "exec")
    statement = parse(source).body[0]

    assert isinstance(statement, ast.WithStatement)
    assert len(statement.items) == 2
    assert [target.name for _, target in statement.items] == [
        "source", "destination",
    ]


def test_parenthesized_with_explicit_line_joins():
    source = (
        "with (\\\n"
        "    open('input.txt') as source,\\\n"
        "    open('output.txt', 'w') as destination,\\\n"
        "):\n"
        "    destination.write(source.read())\n"
    )
    compile(source, "<test>", "exec")
    statement = parse(source).body[0]

    assert len(statement.items) == 2
    assert statement.body[0].expression.function.attribute == "write"


def test_parenthesized_async_with_and_legacy_forms():
    source = (
        "async def run():\n"
        "    async with (first() as one, second() as two,):\n"
        "        await one.read()\n"
        "with first() as one, second() as two:\n"
        "    use(one, two)\n"
        "with first() as one:\n"
        "    use(one)\n"
    )
    compile(source, "<test>", "exec")
    tree = parse(source)

    async_with = tree.body[0].body[0]
    assert async_with.is_async is True
    assert len(async_with.items) == 2
    assert len(tree.body[1].items) == 2
    assert len(tree.body[2].items) == 1


def test_parenthesized_context_expression_with_outer_as_target():
    source = (
        "with (first()) as manager:\n"
        "    use(manager)\n"
        "with (first(), second()) as pair:\n"
        "    use(pair)\n"
        "with (first(),) as singleton:\n"
        "    use(singleton)\n"
    )
    compile(source, "<test>", "exec")
    statements = parse(source).body

    assert len(statements[0].items) == 1
    assert isinstance(statements[0].items[0][0], ast.CallExpression)
    assert statements[0].items[0][1].name == "manager"
    assert isinstance(statements[1].items[0][0], ast.TupleExpression)
    assert len(statements[1].items[0][0].elements) == 2
    assert isinstance(statements[2].items[0][0], ast.TupleExpression)
    assert len(statements[2].items[0][0].elements) == 1


def test_empty_tuple_context_expression_remains_valid():
    source = "with ():\n    pass\n"
    compile(source, "<test>", "exec")
    statement = parse(source).body[0]

    assert len(statement.items) == 1
    assert isinstance(statement.items[0][0], ast.TupleExpression)
    assert statement.items[0][0].elements == []


@pytest.mark.parametrize(
    "source",
    [
        "with (first(), second():\n    pass\n",
        "with (first() as one second() as two):\n    pass\n",
        "with (first(),, second()):\n    pass\n",
        "with (first() as inner, second()) as outer:\n    pass\n",
    ],
)
def test_invalid_parenthesized_with_syntax_matches_cpython(source):
    with pytest.raises(SyntaxError):
        compile(source, "<test>", "exec")

    with pytest.raises(ParserError):
        parse(source)
