
from polylint.languages.python.tokens import Token, TokenType


KEYWORDS = {
    "False", "None", "True",
    "and", "as", "assert", "async", "await",
    "break", "class", "continue",
    "def", "del",
    "elif", "else", "except",
    "finally", "for", "from",
    "global",
    "if", "import", "in", "is",
    "lambda",
    "nonlocal", "not",
    "or",
    "pass",
    "raise", "return",
    "try",
    "while", "with",
    "yield",
}


OPERATORS = {
    "**=", "//=", "<<=", ">>=",
    "==", "!=", "<=", ">=",
    "+=", "-=", "*=", "/=", "%=",
    "**", "//", "<<", ">>",
    "@=", ":=", "->",
    "+", "-", "*", "/", "%",
    "=", "<", ">", "!",
    "@", "&", "|", "^", "~",
}


STRING_PREFIXES = {
    "r", "R", "f", "F", "b", "B", "u", "U",
    "br", "Br", "bR", "BR",
    "rb", "Rb", "rB", "RB",
    "fr", "Fr", "fR", "FR",
    "rf", "Rf", "rF", "RF",
}


class Lexer:

    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.line = 1
        self.column = 1
        self.indent_stack = [0]
        self.at_line_start = True
        self.delimiter_depth = 0

    def tokenize(self):
        tokens = []

        while self.position < len(self.source):

            if self.at_line_start:

                if self.delimiter_depth > 0:
                    while (
                        self.position < len(self.source)
                        and self.source[self.position] in " \t"
                    ):
                        self.advance()

                    self.at_line_start = False

                else:
                    indentation = 0

                    while (
                        self.position < len(self.source)
                        and self.source[self.position] in " \t"
                    ):
                        if self.source[self.position] == " ":
                            indentation += 1
                        else:
                            indentation += 8 - (indentation % 8)

                        self.advance()

                    if (
                        self.position < len(self.source)
                        and self.source[self.position] == "\n"
                    ):
                        self.advance()
                        continue

                    if (
                        self.position < len(self.source)
                        and self.source[self.position] == "#"
                    ):
                        while (
                            self.position < len(self.source)
                            and self.source[self.position] != "\n"
                        ):
                            self.advance()
                        continue

                    if indentation > self.indent_stack[-1]:
                        self.indent_stack.append(indentation)
                        tokens.append(
                            Token(
                                TokenType.INDENT,
                                "",
                                self.line,
                                self.column
                            )
                        )

                    elif indentation < self.indent_stack[-1]:
                        while indentation < self.indent_stack[-1]:
                            self.indent_stack.pop()
                            tokens.append(
                                Token(
                                    TokenType.DEDENT,
                                    "",
                                    self.line,
                                    self.column
                                )
                            )

                        if indentation != self.indent_stack[-1]:
                            raise IndentationError(
                                f"Inconsistent indentation at line {self.line}"
                            )

                    self.at_line_start = False

            if self.position >= len(self.source):
                break

            char = self.source[self.position]

            # Newlines
            if char == "\n":
                if self.delimiter_depth == 0:
                    tokens.append(
                        Token(
                            TokenType.NEWLINE,
                            "\n",
                            self.line,
                            self.column
                        )
                    )

                self.advance()
                self.at_line_start = True
                continue

            # Whitespace
            if char.isspace():
                self.advance()
                continue

            # Comments
            if char == "#":
                while (
                    self.position < len(self.source)
                    and self.source[self.position] != "\n"
                ):
                    self.advance()
                continue

            # Ellipsis
            if self.source.startswith("...", self.position):
                tokens.append(
                    Token(
                        TokenType.PUNCTUATION,
                        "...",
                        self.line,
                        self.column
                    )
                )

                self.advance()
                self.advance()
                self.advance()
                continue

            # Strings
            if char in "'\"" or self.is_string_start():
                tokens.append(self.read_string())
                continue

            # Identifiers and keywords
            if char.isalpha() or char == "_":
                tokens.append(self.read_identifier())
                continue

            # Numbers
            if char.isdigit():
                tokens.append(self.read_number())
                continue

            # Operators
            if char in "+-*/%=<>!@&|^~":
                tokens.append(self.read_operator())
                continue

            # Walrus operator
            if self.source.startswith(":=", self.position):
                tokens.append(self.read_operator())
                continue

            # Punctuation
            if char in "(){}[],.:;":
                line = self.line
                column = self.column

                if char in "([{":
                    self.delimiter_depth += 1

                elif char in ")]}":
                    self.delimiter_depth = max(
                        0,
                        self.delimiter_depth - 1
                    )

                tokens.append(
                    Token(
                        TokenType.PUNCTUATION,
                        char,
                        line,
                        column
                    )
                )

                self.advance()
                continue

            raise SyntaxError(
                f"Unexpected character '{char}' "
                f"at line {self.line}, column {self.column}"
            )

        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(
                Token(
                    TokenType.DEDENT,
                    "",
                    self.line,
                    self.column
                )
            )

        tokens.append(
            Token(
                TokenType.EOF,
                "",
                self.line,
                self.column
            )
        )

        return tokens

    def advance(self):
        if self.position >= len(self.source):
            return

        char = self.source[self.position]
        self.position += 1

        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

    def is_string_start(self):
        if (
            self.position >= len(self.source)
            or not self.source[self.position].isalpha()
        ):
            return False

        for prefix in sorted(
            STRING_PREFIXES,
            key=len,
            reverse=True
        ):
            if self.source.startswith(prefix, self.position):
                quote_position = self.position + len(prefix)

                if (
                    quote_position < len(self.source)
                    and self.source[quote_position] in "'\""
                ):
                    return True

        return False

    def read_identifier(self):
        start = self.position
        line = self.line
        column = self.column

        while (
            self.position < len(self.source)
            and (
                self.source[self.position].isalnum()
                or self.source[self.position] == "_"
            )
        ):
            self.advance()

        value = self.source[start:self.position]

        token_type = (
            TokenType.KEYWORD
            if value in KEYWORDS
            else TokenType.IDENTIFIER
        )

        return Token(token_type, value, line, column)

    def read_number(self):
        start = self.position
        line = self.line
        column = self.column

        prefixes = {
            "0b": "01",
            "0B": "01",
            "0o": "01234567",
            "0O": "01234567",
            "0x": "0123456789abcdefABCDEF",
            "0X": "0123456789abcdefABCDEF",
        }

        prefix = self.source[self.position:self.position + 2]

        if prefix in prefixes:
            valid_digits = prefixes[prefix]
            self.advance()
            self.advance()

            digit_count = 0
            previous_underscore = False

            while self.position < len(self.source):
                char = self.source[self.position]

                if char in valid_digits:
                    digit_count += 1
                    previous_underscore = False
                    self.advance()

                elif char == "_":
                    if digit_count == 0 or previous_underscore:
                        raise SyntaxError(
                            f"Invalid numeric separator "
                            f"at line {line}, column {column}"
                        )

                    previous_underscore = True
                    self.advance()

                else:
                    break

            if digit_count == 0 or previous_underscore:
                raise SyntaxError(
                    f"Invalid number at line {line}, column {column}"
                )

            return Token(
                TokenType.INTEGER,
                self.source[start:self.position],
                line,
                column
            )

        token_type = TokenType.INTEGER
        previous_underscore = False
        digit_count = 0

        while self.position < len(self.source):
            char = self.source[self.position]

            if char.isdigit():
                digit_count += 1
                previous_underscore = False
                self.advance()

            elif char == "_":
                if digit_count == 0 or previous_underscore:
                    raise SyntaxError(
                        f"Invalid numeric separator "
                        f"at line {line}, column {column}"
                    )

                previous_underscore = True
                self.advance()

            else:
                break

        if previous_underscore:
            raise SyntaxError(
                f"Invalid numeric separator "
                f"at line {line}, column {column}"
            )

        # Decimal fraction
        if (
            self.position < len(self.source)
            and self.source[self.position] == "."
            and self.position + 1 < len(self.source)
            and self.source[self.position + 1].isdigit()
        ):
            token_type = TokenType.FLOAT
            self.advance()

            fraction_digits = 0
            previous_underscore = False

            while self.position < len(self.source):
                char = self.source[self.position]

                if char.isdigit():
                    fraction_digits += 1
                    previous_underscore = False
                    self.advance()

                elif char == "_":
                    if fraction_digits == 0 or previous_underscore:
                        raise SyntaxError(
                            f"Invalid numeric separator "
                            f"at line {line}, column {column}"
                        )

                    previous_underscore = True
                    self.advance()

                else:
                    break

            if previous_underscore:
                raise SyntaxError(
                    f"Invalid numeric separator "
                    f"at line {line}, column {column}"
                )

        # Scientific notation
        if (
            self.position < len(self.source)
            and self.source[self.position] in "eE"
        ):
            token_type = TokenType.FLOAT
            self.advance()

            if (
                self.position < len(self.source)
                and self.source[self.position] in "+-"
            ):
                self.advance()

            exponent_start = self.position
            previous_underscore = False

            while self.position < len(self.source):
                char = self.source[self.position]

                if char.isdigit():
                    previous_underscore = False
                    self.advance()

                elif char == "_":
                    if (
                        self.position == exponent_start
                        or previous_underscore
                    ):
                        raise SyntaxError(
                            f"Invalid exponent "
                            f"at line {line}, column {column}"
                        )

                    previous_underscore = True
                    self.advance()

                else:
                    break

            if (
                self.position == exponent_start
                or previous_underscore
            ):
                raise SyntaxError(
                    f"Invalid exponent "
                    f"at line {line}, column {column}"
                )

        return Token(
            token_type,
            self.source[start:self.position],
            line,
            column
        )

    def read_operator(self):
        line = self.line
        column = self.column

        for operator in sorted(
            OPERATORS,
            key=len,
            reverse=True
        ):
            if self.source.startswith(operator, self.position):
                for _ in operator:
                    self.advance()

                return Token(
                    TokenType.OPERATOR,
                    operator,
                    line,
                    column
                )

        raise SyntaxError(
            f"Unknown operator at line {line}, column {column}"
        )

    def read_string(self):
        start = self.position
        line = self.line
        column = self.column

        prefix = ""

        for candidate in sorted(
            STRING_PREFIXES,
            key=len,
            reverse=True
        ):
            if self.source.startswith(candidate, self.position):
                quote_position = self.position + len(candidate)

                if (
                    quote_position < len(self.source)
                    and self.source[quote_position] in "'\""
                ):
                    prefix = candidate
                    break

        for _ in prefix:
            self.advance()

        if self.position >= len(self.source):
            raise SyntaxError(
                f"Unterminated string at line {line}, column {column}"
            )

        quote = self.source[self.position]

        triple = self.source.startswith(
            quote * 3,
            self.position
        )

        if triple:
            delimiter = quote * 3
            self.advance()
            self.advance()
            self.advance()
        else:
            delimiter = quote
            self.advance()

        while self.position < len(self.source):

            if self.source.startswith(delimiter, self.position):
                for _ in delimiter:
                    self.advance()

                return Token(
                    TokenType.STRING,
                    self.source[start:self.position],
                    line,
                    column
                )

            char = self.source[self.position]

            if char == "\\":
                self.advance()

                if self.position >= len(self.source):
                    raise SyntaxError(
                        f"Unterminated string "
                        f"at line {line}, column {column}"
                    )

                self.advance()
                continue

            if char == "\n" and not triple:
                raise SyntaxError(
                    f"Unterminated string "
                    f"at line {line}, column {column}"
                )

            self.advance()

        raise SyntaxError(
            f"Unterminated string at line {line}, column {column}"
        )
