
import pytest

from polylint.languages.python.lexer import Lexer
from polylint.languages.python.tokens import TokenType


def get_tokens(source):
    return [
        token
        for token in Lexer(source).tokenize()
        if token.type != TokenType.EOF
    ]


# ============================================================
# 1. BASIC TOKENIZATION
# ============================================================

def test_basic_tokenization():
    tokens = Lexer("total = price + tax").tokenize()

    assert tokens[0].value == "total"
    assert tokens[0].type == TokenType.IDENTIFIER
    assert tokens[1].value == "="
    assert tokens[2].value == "price"
    assert tokens[4].value == "tax"
    assert tokens[-1].type == TokenType.EOF


def test_multiple_identifiers():
    tokens = Lexer("name age salary").tokenize()

    identifiers = [
        t.value for t in tokens
        if t.type == TokenType.IDENTIFIER
    ]

    assert identifiers == ["name", "age", "salary"]


def test_identifier_with_underscore():
    tokens = Lexer("student_name").tokenize()
    assert tokens[0].value == "student_name"
    assert tokens[0].type == TokenType.IDENTIFIER


def test_identifier_with_numbers():
    tokens = Lexer("student123").tokenize()
    assert tokens[0].value == "student123"
    assert tokens[0].type == TokenType.IDENTIFIER


def test_identifier_starting_with_underscore():
    tokens = Lexer("_private").tokenize()
    assert tokens[0].value == "_private"


def test_empty_source():
    tokens = Lexer("").tokenize()
    assert len(tokens) == 1
    assert tokens[0].type == TokenType.EOF


def test_whitespace_handling():
    tokens = Lexer("x    =     10").tokenize()
    values = [t.value for t in tokens]
    assert values == ["x", "=", "10", ""]


# ============================================================
# 2. KEYWORDS
# ============================================================

@pytest.mark.parametrize(
    "keyword",
    [
        "if", "else", "elif",
        "for", "while",
        "def", "class",
        "return", "import", "from",
        "as", "pass", "break",
        "continue", "True", "False", "None",
    ],
)
def test_keywords(keyword):
    tokens = Lexer(keyword).tokenize()
    assert tokens[0].type == TokenType.KEYWORD
    assert tokens[0].value == keyword


def test_keyword_like_identifier():
    tokens = Lexer("ifelse").tokenize()
    assert tokens[0].type == TokenType.IDENTIFIER


# ============================================================
# 3. OPERATORS
# ============================================================

@pytest.mark.parametrize(
    "operator",
    [
        "+", "-", "*", "/", "%",
        "=", "<", ">", "!",
        "==", "!=", "<=", ">=",
        "+=", "-=", "*=", "/=", "%=",
        "**", "//", "**=", "//=",
        "@", "&", "|", "^", "~",
        "<<", ">>", "<<=", ">>=",
        "@=", ":=", "->",
    ],
)
def test_operators(operator):
    tokens = get_tokens(f"x {operator} y")

    assert tokens[1].type == TokenType.OPERATOR
    assert tokens[1].value == operator


def test_multi_character_operators():
    tokens = Lexer("x == 10").tokenize()
    assert tokens[1].value == "=="


def test_longest_operator_match():
    tokens = Lexer("x **= 2").tokenize()
    assert tokens[1].value == "**="


def test_ellipsis_operator():
    tokens = get_tokens("...")
    assert len(tokens) == 1
    assert tokens[0].value == "..."
    assert tokens[0].type == TokenType.PUNCTUATION


# ============================================================
# 4. PUNCTUATION
# ============================================================

@pytest.mark.parametrize(
    "punctuation",
    ["(", ")", "{", "}", "[", "]", ",", ".", ":", ";"],
)
def test_punctuation(punctuation):
    tokens = Lexer(punctuation).tokenize()
    assert tokens[0].type == TokenType.PUNCTUATION
    assert tokens[0].value == punctuation


# ============================================================
# 5. STRINGS
# ============================================================

def test_double_quoted_string():
    tokens = Lexer('name = "Amulya"').tokenize()
    assert tokens[2].type == TokenType.STRING
    assert tokens[2].value == '"Amulya"'


def test_single_quoted_string():
    tokens = Lexer("message = 'Hello'").tokenize()
    assert tokens[2].type == TokenType.STRING
    assert tokens[2].value == "'Hello'"


def test_string_with_spaces():
    tokens = Lexer('"Hello world"').tokenize()
    assert tokens[0].value == '"Hello world"'


def test_empty_string():
    tokens = Lexer('""').tokenize()
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == '""'


def test_string_with_escaped_quote():
    tokens = Lexer(r'"Hello \"world\""').tokenize()
    assert tokens[0].type == TokenType.STRING


def test_string_with_escaped_backslash():
    tokens = Lexer(r'"C:\\Users\\Student"').tokenize()
    assert tokens[0].type == TokenType.STRING


def test_unterminated_double_string():
    with pytest.raises(SyntaxError):
        Lexer('"Hello').tokenize()


def test_unterminated_single_string():
    with pytest.raises(SyntaxError):
        Lexer("'Hello").tokenize()


def test_string_with_unescaped_newline():
    with pytest.raises(SyntaxError):
        Lexer('"Hello\nworld"').tokenize()


# ============================================================
# 6. STRING PREFIXES
# ============================================================

@pytest.mark.parametrize(
    "source",
    [
        'r"hello"',
        'f"hello {name}"',
        'b"hello"',
        'u"hello"',
        'R"hello"',
        'F"hello"',
        'B"hello"',
        'U"hello"',
    ],
)
def test_string_prefixes(source):
    tokens = get_tokens(source)

    assert len(tokens) == 1
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == source


@pytest.mark.parametrize(
    "source",
    [
        'rf"hello {name}"',
        'fr"hello {name}"',
        'rb"hello"',
        'br"hello"',
    ],
)
def test_combined_string_prefixes(source):
    tokens = get_tokens(source)

    assert len(tokens) == 1
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == source


def test_fstring_token_scans_quotes_inside_replacement_fields():
    source = 'f"{mapping["key"]}"'
    tokens = get_tokens(source)

    assert len(tokens) == 1
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == source


def test_raw_multiline_fstring_remains_one_string_token():
    source = 'rf"""path={path}\\n{name}"""'
    tokens = get_tokens(source)

    assert len(tokens) == 1
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == source


# ============================================================
# 7. TRIPLE-QUOTED STRINGS
# ============================================================

@pytest.mark.parametrize(
    "source",
    [
        "'''hello'''",
        '"""hello"""',
        '"""hello\nworld"""',
        "'''hello\nworld'''",
        '"""multiple\nlines\nhere"""',
    ],
)
def test_triple_quoted_strings(source):
    tokens = get_tokens(source)

    assert len(tokens) == 1
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == source


def test_unterminated_triple_quoted_string():
    with pytest.raises(SyntaxError):
        Lexer('"""hello').tokenize()


# ============================================================
# 8. COMMENTS
# ============================================================

def test_single_line_comment():
    tokens = Lexer("# This is a comment\nx = 10").tokenize()
    values = [t.value for t in tokens]

    assert "#" not in values
    assert "This" not in values
    assert "x" in values


def test_inline_comment():
    tokens = Lexer("x = 10 # comment").tokenize()
    values = [t.value for t in tokens]

    assert values == ["x", "=", "10", ""]


def test_comment_only_source():
    tokens = Lexer("# comment").tokenize()
    assert all(t.type == TokenType.EOF for t in tokens)


def test_comment_after_code():
    tokens = Lexer("x = 10 # comment\ny = 20").tokenize()

    identifiers = [
        t.value for t in tokens
        if t.type == TokenType.IDENTIFIER
    ]

    assert identifiers == ["x", "y"]


# ============================================================
# 9. NEWLINES
# ============================================================

def test_newline_tokens():
    tokens = Lexer("x = 10\ny = 20").tokenize()

    newlines = [
        t for t in tokens
        if t.type == TokenType.NEWLINE
    ]

    assert len(newlines) == 1
    assert newlines[0].value == "\n"
    assert newlines[0].line == 1


def test_multiple_newlines():
    tokens = Lexer("x = 1\ny = 2\nz = 3").tokenize()

    newlines = [
        t for t in tokens
        if t.type == TokenType.NEWLINE
    ]

    assert len(newlines) == 2


def test_blank_lines():
    tokens = Lexer("x = 1\n\ny = 2").tokenize()

    identifiers = [
        t.value for t in tokens
        if t.type == TokenType.IDENTIFIER
    ]

    assert identifiers == ["x", "y"]


def test_newline_at_end_of_source():
    tokens = Lexer("x = 10\n").tokenize()

    assert sum(
        t.type == TokenType.NEWLINE for t in tokens
    ) == 1


# ============================================================
# 10. INDENTATION AND DEDENTATION
# ============================================================

def test_indent_token():
    tokens = Lexer("if True:\n    x = 10").tokenize()

    assert sum(
        t.type == TokenType.INDENT for t in tokens
    ) == 1


def test_dedent_token():
    tokens = Lexer("if True:\n    x = 10\ny = 20").tokenize()

    assert sum(
        t.type == TokenType.DEDENT for t in tokens
    ) == 1


def test_nested_indentation():
    tokens = Lexer(
        "if True:\n    if False:\n        x = 10\ny = 20"
    ).tokenize()

    assert sum(
        t.type == TokenType.INDENT for t in tokens
    ) == 2

    assert sum(
        t.type == TokenType.DEDENT for t in tokens
    ) == 2


def test_multiple_dedents():
    tokens = Lexer(
        "if True:\n"
        "    if False:\n"
        "        x = 10\n"
        "    y = 20\n"
        "z = 30\n"
    ).tokenize()

    assert sum(
        t.type == TokenType.DEDENT for t in tokens
    ) == 2


def test_inconsistent_indentation():
    source = "if True:\n    x = 10\n  y = 20"

    with pytest.raises(IndentationError):
        Lexer(source).tokenize()


def test_comment_inside_indented_block():
    source = "if True:\n    # comment\n    x = 10"
    tokens = Lexer(source).tokenize()

    assert sum(
        t.type == TokenType.INDENT for t in tokens
    ) == 1


def test_tab_indentation():
    tokens = Lexer("\tvalue = 10").tokenize()

    assert any(
        t.type == TokenType.INDENT for t in tokens
    )


def test_blank_lines_do_not_create_indentation():
    source = "if True:\n\n    value = 10\n"
    tokens = Lexer(source).tokenize()

    assert sum(
        t.type == TokenType.INDENT for t in tokens
    ) == 1


# ============================================================
# 11. INTEGER NUMBERS
# ============================================================

def test_integer_number():
    tokens = Lexer("age = 20").tokenize()
    assert tokens[2].type == TokenType.INTEGER
    assert tokens[2].value == "20"


def test_zero_integer():
    tokens = Lexer("x = 0").tokenize()
    assert tokens[2].type == TokenType.INTEGER


def test_large_integer():
    tokens = Lexer("x = 123456789").tokenize()
    assert tokens[2].value == "123456789"


def test_binary_number():
    tokens = Lexer("x = 0b1010").tokenize()
    assert tokens[2].type == TokenType.INTEGER
    assert tokens[2].value == "0b1010"


def test_octal_number():
    tokens = Lexer("x = 0o17").tokenize()
    assert tokens[2].type == TokenType.INTEGER
    assert tokens[2].value == "0o17"


def test_hexadecimal_number():
    tokens = Lexer("x = 0xFF").tokenize()
    assert tokens[2].type == TokenType.INTEGER
    assert tokens[2].value == "0xFF"


def test_number_with_underscores():
    tokens = Lexer("x = 1_000_000").tokenize()
    assert tokens[2].type == TokenType.INTEGER
    assert tokens[2].value == "1_000_000"


# ============================================================
# 12. FLOAT NUMBERS
# ============================================================

def test_float_number():
    tokens = Lexer("price = 19.99").tokenize()
    assert tokens[2].type == TokenType.FLOAT
    assert tokens[2].value == "19.99"


def test_multiple_float_numbers():
    tokens = Lexer("x = 0.5\ny = 100.0").tokenize()

    floats = [
        t.value for t in tokens
        if t.type == TokenType.FLOAT
    ]

    assert floats == ["0.5", "100.0"]


def test_float_with_many_decimal_places():
    tokens = Lexer("x = 3.14159265").tokenize()
    assert tokens[2].type == TokenType.FLOAT


@pytest.mark.parametrize(
    "source",
    [
        "0.5",
        "1.25",
        "12.0",
        "1_000.25",
    ],
)
def test_decimal_float_edge_cases(source):
    tokens = get_tokens(source)

    assert len(tokens) == 1
    assert tokens[0].type == TokenType.FLOAT
    assert tokens[0].value == source


# ============================================================
# 13. SCIENTIFIC NOTATION
# ============================================================

def test_scientific_notation():
    tokens = Lexer("x = 1e3").tokenize()
    assert tokens[2].type == TokenType.FLOAT
    assert tokens[2].value == "1e3"


def test_scientific_notation_with_decimal():
    tokens = Lexer("x = 2.5e4").tokenize()
    assert tokens[2].type == TokenType.FLOAT
    assert tokens[2].value == "2.5e4"


def test_scientific_notation_with_negative_exponent():
    tokens = Lexer("x = 3.2E-2").tokenize()
    assert tokens[2].type == TokenType.FLOAT
    assert tokens[2].value == "3.2E-2"


def test_invalid_scientific_notation():
    with pytest.raises(SyntaxError):
        Lexer("x = 1e").tokenize()


# ============================================================
# 14. INVALID NUMBERS
# ============================================================

@pytest.mark.parametrize(
    "source",
    [
        "0b",
        "0o8",
        "0xG",
        "1__0",
        "1_",
        "1e",
    ],
)
def test_invalid_numbers(source):
    with pytest.raises(SyntaxError):
        Lexer(source).tokenize()


# ============================================================
# 15. NEWLINES INSIDE BRACKETS
# ============================================================

def test_newline_inside_parentheses():
    source = "value = (1 +\n2)"
    tokens = get_tokens(source)

    assert not any(
        t.type == TokenType.NEWLINE for t in tokens
    )


def test_newline_inside_square_brackets():
    source = "values = [1,\n2,\n3]"
    tokens = get_tokens(source)

    assert not any(
        t.type == TokenType.NEWLINE for t in tokens
    )


def test_newline_inside_curly_braces():
    source = 'data = {"a": 1,\n"b": 2}'
    tokens = get_tokens(source)

    assert not any(
        t.type == TokenType.NEWLINE for t in tokens
    )


def test_newline_outside_brackets():
    source = "first = 1\nsecond = 2"
    tokens = get_tokens(source)

    assert any(
        t.type == TokenType.NEWLINE for t in tokens
    )


# ============================================================
# 16. ERROR HANDLING
# ============================================================

def test_unexpected_character():
    with pytest.raises(SyntaxError):
        Lexer("x = 10 $ y").tokenize()


def test_unterminated_escape_sequence():
    with pytest.raises(SyntaxError):
        Lexer('"hello\\').tokenize()


# ============================================================
# 17. TOKEN POSITION TRACKING
# ============================================================

def test_token_line_number():
    tokens = Lexer("x = 10\ny = 20").tokenize()

    y_token = next(
        t for t in tokens
        if t.value == "y"
    )

    assert y_token.line == 2


def test_token_column_number():
    tokens = Lexer("x = 10").tokenize()

    assert tokens[0].column == 1
    assert tokens[1].column == 3
    assert tokens[2].column == 5


def test_identifier_position_after_newline():
    tokens = get_tokens("first\nsecond")

    second = next(
        t for t in tokens
        if t.value == "second"
    )

    assert second.line == 2
    assert second.column == 1


def test_operator_position():
    tokens = get_tokens("value = 10")

    operator = next(
        t for t in tokens
        if t.value == "="
    )

    assert operator.line == 1
    assert operator.column == 7


def test_string_position():
    tokens = get_tokens('name = "hello"')

    string = next(
        t for t in tokens
        if t.type == TokenType.STRING
    )

    assert string.line == 1
    assert string.column == 8


def test_token_position_on_third_line():
    tokens = get_tokens("a = 1\nb = 2\nc = 3")

    third = next(
        t for t in tokens
        if t.value == "c"
    )

    assert third.line == 3
    assert third.column == 1


# ============================================================
# 18. EOF
# ============================================================

def test_eof_token():
    tokens = Lexer("x = 10").tokenize()
    assert tokens[-1].type == TokenType.EOF


def test_eof_token_value():
    tokens = Lexer("x = 10").tokenize()
    assert tokens[-1].value == ""
