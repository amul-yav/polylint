
import pytest

from polylint.formatter.python_formatter import (
    FormatterConfig,
    PythonFormatter,
)


@pytest.fixture
def formatter():
    return PythonFormatter()


def test_empty_source(formatter):
    assert formatter.format_code("") == "\n"


def test_empty_source_without_final_newline():
    formatter = PythonFormatter(
        FormatterConfig(final_newline=False)
    )

    assert formatter.format_code("") == ""


def test_final_newline(formatter):
    result = formatter.format_code("x = 1")

    assert result.endswith("\n")


def test_no_final_newline():
    formatter = PythonFormatter(
        FormatterConfig(final_newline=False)
    )

    assert formatter.format_code("x = 1") == "x = 1"


def test_remove_trailing_whitespace(formatter):
    result = formatter.format_code("x = 1   \n")

    assert result == "x = 1\n"


def test_remove_trailing_whitespace_disabled():
    formatter = PythonFormatter(
        FormatterConfig(remove_trailing_whitespace=False)
    )

    result = formatter.format_code("x = 1   ")

    assert result == "x = 1\n"


def test_spaces_around_assignment(formatter):
    result = formatter.format_code("x=1")

    assert result == "x = 1\n"


def test_spaces_around_addition(formatter):
    result = formatter.format_code("x=1+2")

    assert result == "x = 1 + 2\n"


def test_comma_spacing(formatter):
    result = formatter.format_code("x=[1,2,3]")

    assert result == "x = [1, 2, 3]\n"


def test_function_call_spacing(formatter):
    result = formatter.format_code("print('hello')")

    assert result == "print('hello')\n"


def test_preserve_string_contents(formatter):
    result = formatter.format_code('x="hello  world"')

    assert result == 'x = "hello  world"\n'


def test_preserve_comment(formatter):
    result = formatter.format_code("x=1# comment")

    assert result == "x = 1 # comment\n"


def test_indent_size_configuration():
    formatter = PythonFormatter(
        FormatterConfig(indent_size=2)
    )

    source = "if True:\n    x=1"

    result = formatter.format_code(source)

    assert "  x = 1" in result


def test_default_indent_size(formatter):
    source = "if True:\n    x=1"

    result = formatter.format_code(source)

    assert "    x = 1" in result


def test_multiple_statements(formatter):
    source = "x=1\ny=2"

    result = formatter.format_code(source)

    assert result == "x = 1\ny = 2\n"


def test_function_definition(formatter):
    source = "def hello():\n    print('hi')"

    result = formatter.format_code(source)

    assert "def hello():" in result
    assert "    print('hi')" in result


def test_invalid_indent_size():
    with pytest.raises(ValueError):
        PythonFormatter(FormatterConfig(indent_size=0))


def test_invalid_max_line_length():
    with pytest.raises(ValueError):
        PythonFormatter(
            FormatterConfig(max_line_length=0)
        )


def test_idempotence(formatter):
    source = "x=1+2\nprint(x)"

    once = formatter.format_code(source)
    twice = formatter.format_code(once)

    assert once == twice


def test_multiline_string(formatter):
    source = 'x="""hello\nworld"""'

    result = formatter.format_code(source)

    assert '"""hello\nworld"""' in result


def test_return_statement(formatter):
    source = "def f():\n    return  10"

    result = formatter.format_code(source)

    assert "return 10" in result


def test_colon_spacing(formatter):
    result = formatter.format_code("if x==1:\n    pass")

    assert "if x == 1:" in result


def test_parentheses(formatter):
    result = formatter.format_code("x=(1+2)")

    assert result == "x = (1 + 2)\n"


def test_blank_source_lines(formatter):
    source = "x=1\n\ny=2"

    result = formatter.format_code(source)

    assert "\n\n" in result
