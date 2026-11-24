
from polylint.languages.python.tokens import Token, TokenType
from polylint.languages.python.lexer import Lexer
from polylint.languages.python import ast_nodes as ast


class ParserError(Exception):
    """Raised when the parser encounters invalid syntax."""

    def __init__(self, message: str, token: Token | None = None):
        self.token = token
        if token is not None:
            message = (
                f"{message} at line {token.line}, "
                f"column {token.column} (got {token.value!r})"
            )
        super().__init__(message)


class Parser:
    """
    Recursive-descent statement parser with a Pratt expression parser.

    Usage:
        tokens = Lexer(source).tokenize()
        tree = Parser(tokens).parse()
    """

    PRECEDENCE = {
        ":=": 1,
        "or": 2,
        "and": 3,
        "not": 4,
        "in": 5,
        "not in": 5,
        "is": 5,
        "is not": 5,
        "==": 5,
        "!=": 5,
        "<": 5,
        "<=": 5,
        ">": 5,
        ">=": 5,
        "|": 6,
        "^": 7,
        "&": 8,
        "<<": 9,
        ">>": 9,
        "+": 10,
        "-": 10,
        "*": 11,
        "@": 11,
        "/": 11,
        "//": 11,
        "%": 11,
        "**": 12,
    }

    COMPARISON_OPERATORS = {
        "==", "!=", "<", "<=", ">", ">=",
        "in", "is", "not in", "is not",
    }

    AUGMENTED_OPERATORS = {
        "+=", "-=", "*=", "/=", "//=", "%=",
        "**=", "&=", "|=", "^=", ">>=", "<<=", "@=",
    }

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0
        self._in_async_function = False

    # ==========================================
    # Token utilities
    # ==========================================

    @property
    def current(self) -> Token:
        if self.position >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[self.position]

    def peek(self, offset: int = 1) -> Token:
        index = self.position + offset
        if index >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[index]

    def advance(self) -> Token:
        token = self.current
        if token.type != TokenType.EOF:
            self.position += 1
        return token

    def check(self, value: str) -> bool:
        return self.current.value == value

    def check_type(self, token_type: TokenType) -> bool:
        return self.current.type == token_type

    def match(self, *values: str) -> bool:
        if self.current.value in values:
            self.advance()
            return True
        return False

    def expect(self, value: str) -> Token:
        if not self.check(value):
            raise ParserError(f"Expected {value!r}", self.current)
        return self.advance()

    def expect_type(self, token_type: TokenType) -> Token:
        if not self.check_type(token_type):
            raise ParserError(
                f"Expected token type {token_type.name}",
                self.current,
            )
        return self.advance()

    def skip_newlines(self) -> None:
        while self.check_type(TokenType.NEWLINE):
            self.advance()

    def location(self) -> tuple[int, int]:
        return self.current.line, self.current.column

    # ==========================================
    # Entry point
    # ==========================================

    def parse(self) -> ast.Module:
        line, column = self.location()
        body = []

        self.skip_newlines()

        while not self.check_type(TokenType.EOF):
            if self.check_type(TokenType.DEDENT):
                raise ParserError("Unexpected indentation", self.current)

            body.extend(self.parse_statement())
            self.skip_newlines()

        return ast.Module(line=line, column=column, body=body)

    # ==========================================
    # Statements
    # ==========================================

    def parse_statement(self) -> list[ast.ASTNode]:
        if self.check("@"):
            return [self.parse_decorated_definition()]

        if self.check("match") and self._looks_like_match_statement():
            return [self.parse_match_statement()]

        if self.match("async"):
            if self.match("def"):
                return [self.parse_function_definition(is_async=True)]
            if self.match("for"):
                return [self.parse_for_statement(is_async=True)]
            if self.match("with"):
                return [self.parse_with_statement(is_async=True)]
            raise ParserError("Expected def, for or with after async", self.current)

        if self.match("def"):
            return [self.parse_function_definition()]

        if self.match("class"):
            return [self.parse_class_definition()]

        if self.match("if"):
            return [self.parse_if_statement()]

        if self.match("while"):
            return [self.parse_while_statement()]

        if self.match("for"):
            return [self.parse_for_statement()]

        if self.match("try"):
            return [self.parse_try_statement()]

        if self.match("with"):
            return [self.parse_with_statement()]

        return self.parse_simple_statement()

    def _looks_like_match_statement(self) -> bool:
        """Recognize the soft keyword only for a match block header."""
        depth = 0
        for index in range(self.position + 1, len(self.tokens)):
            token = self.tokens[index]
            if token.type == TokenType.NEWLINE and depth == 0:
                return False
            if token.value in ("(", "[", "{"):
                depth += 1
            elif token.value in (")", "]", "}"):
                depth = max(0, depth - 1)
            elif token.value == ":" and depth == 0:
                return (
                    index + 2 < len(self.tokens)
                    and self.tokens[index + 1].type == TokenType.NEWLINE
                    and self.tokens[index + 2].type == TokenType.INDENT
                )
        return False

    def parse_match_statement(self) -> ast.MatchStatement:
        token = self.expect("match")
        subject = self.parse_expression()
        if self.match(","):
            elements = [subject]
            while not self.check(":"):
                elements.append(self.parse_expression())
                if not self.match(","):
                    break
            subject = ast.TupleExpression(
                line=subject.line, column=subject.column, elements=elements,
            )
        self.expect(":")
        if not self.check_type(TokenType.NEWLINE):
            raise ParserError("a match statement requires an indented case block", self.current)
        self.advance()
        self.expect_type(TokenType.INDENT)

        cases = []
        self.skip_newlines()
        while not self.check_type(TokenType.DEDENT) and not self.check_type(TokenType.EOF):
            if not self.check("case"):
                raise ParserError("expected 'case' in match statement", self.current)
            case = self.parse_match_case()
            if cases and cases[-1].guard is None and self._is_irrefutable(cases[-1].pattern):
                raise ParserError("an unguarded irrefutable case must be last", self.current)
            cases.append(case)
            self.skip_newlines()

        self.expect_type(TokenType.DEDENT)
        if not cases:
            raise ParserError("a match statement must contain at least one case", self.current)
        return ast.MatchStatement(
            line=token.line, column=token.column, subject=subject, cases=cases,
        )

    def parse_match_case(self) -> ast.MatchCase:
        token = self.expect("case")
        if self.check("*"):
            pattern = self.parse_pattern_atom(allow_starred=True)
            if not self.check(","):
                raise ParserError("a star pattern must be part of a sequence pattern", self.current)
        else:
            pattern = self.parse_pattern()
        if self.match(","):
            patterns = [pattern]
            while not self.check("if") and not self.check(":"):
                patterns.append(self.parse_pattern(allow_starred=True))
                if not self.match(","):
                    break
            self._validate_star_pattern_count(patterns)
            names = [name for item in patterns for name in self._pattern_capture_names(item)]
            if len(names) != len(set(names)):
                raise ParserError("a pattern cannot bind the same name more than once", self.current)
            pattern = ast.SequencePattern(
                line=pattern.line, column=pattern.column, patterns=patterns,
            )
        guard = self.parse_expression() if self.match("if") else None
        body = self.parse_suite()
        return ast.MatchCase(
            line=token.line, column=token.column,
            pattern=pattern, guard=guard, body=body,
        )

    def parse_pattern(self, *, allow_starred: bool = False) -> ast.ASTNode:
        pattern = self.parse_pattern_atom(allow_starred=allow_starred)
        alternatives = [pattern]
        while self.match("|"):
            alternatives.append(self.parse_pattern_atom(allow_starred=allow_starred))

        if len(alternatives) > 1:
            if any(self._is_irrefutable(item) for item in alternatives[:-1]):
                raise ParserError("an irrefutable pattern must be last in an OR pattern", self.current)
            branch_names = [set(self._pattern_capture_names(item)) for item in alternatives]
            if any(names != branch_names[0] for names in branch_names[1:]):
                raise ParserError("all OR pattern alternatives must bind the same names", self.current)
            pattern = ast.OrPattern(
                line=pattern.line, column=pattern.column, patterns=alternatives,
            )

        if self.match("as"):
            name_token = self.expect_type(TokenType.IDENTIFIER)
            if name_token.value == "_":
                raise ParserError("'_' cannot be used as an AS pattern target", name_token)
            pattern = ast.AsPattern(
                line=pattern.line,
                column=pattern.column,
                pattern=pattern,
                name=ast.CapturePattern(
                    line=name_token.line, column=name_token.column,
                    name=name_token.value,
                ),
            )

        names = self._pattern_capture_names(pattern)
        if len(names) != len(set(names)):
            raise ParserError("a pattern cannot bind the same name more than once", self.current)
        return pattern

    def parse_pattern_atom(self, *, allow_starred: bool = False) -> ast.ASTNode:
        token = self.current
        line, column = token.line, token.column

        if self.match("*"):
            if not allow_starred:
                raise ParserError("star patterns are only allowed in sequences", token)
            inner = self.parse_pattern_atom()
            if not isinstance(inner, (ast.CapturePattern, ast.WildcardPattern)):
                raise ParserError("a star pattern must capture a name or wildcard", token)
            return ast.StarPattern(line=line, column=column, pattern=inner)

        if self.match("["):
            patterns = self.parse_sequence_pattern_items("]")
            return ast.SequencePattern(line=line, column=column, patterns=patterns)

        if self.match("("):
            if self.match(")"):
                return ast.SequencePattern(line=line, column=column, patterns=[])
            first = self.parse_pattern(allow_starred=True)
            if not self.match(","):
                self.expect(")")
                return first
            patterns = [first]
            while not self.check(")") and not self.check_type(TokenType.EOF):
                patterns.append(self.parse_pattern(allow_starred=True))
                if not self.match(","):
                    break
            self.expect(")")
            self._validate_star_pattern_count(patterns)
            return ast.SequencePattern(line=line, column=column, patterns=patterns)

        if self.match("{"):
            return self.parse_mapping_pattern(token)

        if token.value in ("+", "-"):
            sign = -1 if self.advance().value == "-" else 1
            number = self.current
            if number.type not in (TokenType.INTEGER, TokenType.FLOAT):
                raise ParserError("expected a number after pattern sign", number)
            self.advance()
            raw = number.value.replace("_", "")
            try:
                value = float(raw) if number.type == TokenType.FLOAT else int(raw, 0) if raw.lower().startswith(("0x", "0o", "0b")) else int(raw)
            except ValueError:
                raise ParserError("invalid numeric literal pattern", number) from None
            return ast.Literal(line=line, column=column, value=sign * value)

        if token.type in (TokenType.INTEGER, TokenType.FLOAT, TokenType.STRING):
            if token.type == TokenType.STRING and self._is_fstring_literal(token.value):
                raise ParserError("f-strings are not literal patterns", token)
            return self.parse_prefix()

        if token.value in ("True", "False", "None"):
            return self.parse_prefix()

        if token.type == TokenType.IDENTIFIER:
            value = self.parse_dotted_pattern_value()
            if self.check("("):
                return self.parse_class_pattern(value)
            if isinstance(value, ast.Identifier) and value.name == "_":
                return ast.WildcardPattern(line=line, column=column)
            if isinstance(value, ast.Identifier):
                return ast.CapturePattern(line=line, column=column, name=value.name)
            return ast.ValuePattern(line=line, column=column, value=value)

        raise ParserError("expected a pattern", token)

    def parse_sequence_pattern_items(self, closing: str) -> list[ast.ASTNode]:
        patterns = []
        if self.match(closing):
            return patterns
        while True:
            patterns.append(self.parse_pattern(allow_starred=True))
            if not self.match(","):
                break
            if self.check(closing):
                break
        self.expect(closing)
        self._validate_star_pattern_count(patterns)
        return patterns

    def _validate_star_pattern_count(self, patterns: list[ast.ASTNode]) -> None:
        if sum(isinstance(pattern, ast.StarPattern) for pattern in patterns) > 1:
            raise ParserError("a sequence pattern may contain only one star pattern", self.current)

    def parse_mapping_pattern(self, opening: Token) -> ast.MappingPattern:
        entries = []
        rest = None
        keys = set()
        if self.match("}"):
            return ast.MappingPattern(line=opening.line, column=opening.column)

        while True:
            if self.match("**"):
                if rest is not None:
                    raise ParserError("a mapping pattern may contain only one '**' rest pattern", self.current)
                rest_token = self.expect_type(TokenType.IDENTIFIER)
                if rest_token.value == "_":
                    raise ParserError("'_' is not allowed as a mapping rest target", rest_token)
                rest = ast.CapturePattern(
                    line=rest_token.line, column=rest_token.column,
                    name=rest_token.value,
                )
                if self.match(",") and not self.check("}"):
                    raise ParserError("a mapping rest pattern must be last", self.current)
                break

            key = self.parse_mapping_pattern_key()
            if isinstance(key, ast.Literal):
                key_marker = (type(key.value), key.value)
                if key_marker in keys:
                    raise ParserError("duplicate mapping pattern key", self.current)
                keys.add(key_marker)
            self.expect(":")
            value_pattern = self.parse_pattern()
            entries.append((key, value_pattern))
            if not self.match(",") or self.check("}"):
                break

        self.expect("}")
        return ast.MappingPattern(
            line=opening.line, column=opening.column,
            entries=entries, rest=rest,
        )

    def parse_mapping_pattern_key(self) -> ast.ASTNode:
        token = self.current
        if token.value in ("+", "-"):
            sign = -1 if self.advance().value == "-" else 1
            number = self.current
            if number.type not in (TokenType.INTEGER, TokenType.FLOAT):
                raise ParserError("expected a number after pattern key sign", number)
            self.advance()
            raw = number.value.replace("_", "")
            try:
                value = float(raw) if number.type == TokenType.FLOAT else int(raw, 0) if raw.lower().startswith(("0x", "0o", "0b")) else int(raw)
            except ValueError:
                raise ParserError("invalid numeric mapping pattern key", number) from None
            return ast.Literal(line=token.line, column=token.column, value=sign * value)
        if token.type in (TokenType.INTEGER, TokenType.FLOAT, TokenType.STRING) or token.value in ("True", "False", "None"):
            if token.type == TokenType.STRING and self._is_fstring_literal(token.value):
                raise ParserError("f-strings are not mapping pattern keys", token)
            return self.parse_prefix()
        if token.type == TokenType.IDENTIFIER:
            value = self.parse_dotted_pattern_value()
            if isinstance(value, ast.Identifier):
                raise ParserError("a mapping pattern key must be a literal or dotted value", token)
            return value
        raise ParserError("expected a mapping pattern key", token)

    def parse_dotted_pattern_value(self) -> ast.ASTNode:
        token = self.expect_type(TokenType.IDENTIFIER)
        value: ast.ASTNode = ast.Identifier(
            line=token.line, column=token.column, name=token.value,
        )
        while self.match("."):
            attribute = self.expect_type(TokenType.IDENTIFIER)
            value = ast.AttributeAccess(
                line=attribute.line, column=attribute.column,
                object=value, attribute=attribute.value,
            )
        return value

    def parse_class_pattern(self, class_expression: ast.ASTNode) -> ast.ClassPattern:
        opening = self.expect("(")
        positional = []
        keywords = []
        keyword_names = set()
        seen_keyword = False

        while not self.check(")") and not self.check_type(TokenType.EOF):
            if (
                self.current.type == TokenType.IDENTIFIER
                and self.peek().value == "="
            ):
                seen_keyword = True
                name = self.advance().value
                self.advance()
                if name in keyword_names:
                    raise ParserError(f"duplicate class pattern keyword {name!r}", self.current)
                keyword_names.add(name)
                keywords.append((name, self.parse_pattern()))
            else:
                if seen_keyword:
                    raise ParserError("positional patterns cannot follow keyword patterns", self.current)
                positional.append(self.parse_pattern())

            if not self.match(","):
                break

        self.expect(")")
        return ast.ClassPattern(
            line=opening.line, column=opening.column,
            class_expression=class_expression,
            positional_patterns=positional,
            keyword_patterns=keywords,
        )

    def _pattern_capture_names(self, pattern: ast.ASTNode) -> list[str]:
        if isinstance(pattern, ast.CapturePattern):
            return [pattern.name]
        if isinstance(pattern, ast.AsPattern):
            return self._pattern_capture_names(pattern.pattern) + [pattern.name.name]
        if isinstance(pattern, ast.StarPattern):
            return self._pattern_capture_names(pattern.pattern)
        if isinstance(pattern, ast.OrPattern):
            return self._pattern_capture_names(pattern.patterns[0])
        if isinstance(pattern, ast.SequencePattern):
            return [name for item in pattern.patterns for name in self._pattern_capture_names(item)]
        if isinstance(pattern, ast.MappingPattern):
            names = [name for _, item in pattern.entries for name in self._pattern_capture_names(item)]
            if pattern.rest:
                names.append(pattern.rest.name)
            return names
        if isinstance(pattern, ast.ClassPattern):
            names = [name for item in pattern.positional_patterns for name in self._pattern_capture_names(item)]
            names.extend(
                name for _, item in pattern.keyword_patterns
                for name in self._pattern_capture_names(item)
            )
            return names
        return []

    def _is_irrefutable(self, pattern: ast.ASTNode) -> bool:
        if isinstance(pattern, (ast.CapturePattern, ast.WildcardPattern)):
            return True
        if isinstance(pattern, ast.AsPattern):
            return self._is_irrefutable(pattern.pattern)
        if isinstance(pattern, ast.OrPattern):
            return any(self._is_irrefutable(item) for item in pattern.patterns)
        return False

    def parse_simple_statement(self) -> list[ast.ASTNode]:
        statements = [self.parse_small_statement()]

        while self.match(";"):
            if self.check_type(TokenType.NEWLINE) or self.check_type(TokenType.EOF):
                break
            statements.append(self.parse_small_statement())

        if self.check_type(TokenType.NEWLINE):
            self.advance()
        elif not self.check_type(TokenType.EOF) and not self.check_type(TokenType.DEDENT):
            raise ParserError("Expected end of statement", self.current)

        return statements

    def parse_small_statement(self) -> ast.ASTNode:
        line, column = self.location()

        if self.match("pass"):
            return ast.PassStatement(line=line, column=column)

        if self.match("break"):
            return ast.BreakStatement(line=line, column=column)

        if self.match("continue"):
            return ast.ContinueStatement(line=line, column=column)

        if self.match("return"):
            value = None
            if not self.check_type(TokenType.NEWLINE) and not self.check(";"):
                value = self.parse_expression()
            return ast.ReturnStatement(line=line, column=column, value=value)

        if self.match("raise"):
            exception = None
            cause = None
            if not self.check_type(TokenType.NEWLINE) and not self.check(";"):
                exception = self.parse_expression()
                if self.match("from"):
                    cause = self.parse_expression()
            return ast.RaiseStatement(
                line=line, column=column,
                exception=exception, cause=cause,
            )

        if self.match("assert"):
            test = self.parse_expression()
            message = None
            if self.match(","):
                message = self.parse_expression()
            return ast.AssertStatement(
                line=line, column=column, test=test, message=message,
            )

        if self.match("del"):
            targets = [self.parse_expression()]
            while self.match(","):
                targets.append(self.parse_expression())
            return ast.DeleteStatement(
                line=line, column=column, targets=targets,
            )

        if self.match("global"):
            names = [self.expect_type(TokenType.IDENTIFIER).value]
            while self.match(","):
                names.append(self.expect_type(TokenType.IDENTIFIER).value)
            return ast.GlobalStatement(line=line, column=column, names=names)

        if self.match("nonlocal"):
            names = [self.expect_type(TokenType.IDENTIFIER).value]
            while self.match(","):
                names.append(self.expect_type(TokenType.IDENTIFIER).value)
            return ast.NonlocalStatement(line=line, column=column, names=names)

        if self.match("import"):
            return self.parse_import_statement(line, column)

        if self.match("from"):
            return self.parse_import_from_statement(line, column)

        return self.parse_assignment_or_expression()

    def parse_assignment_or_expression(self) -> ast.ASTNode:
        line, column = self.location()
        expression = self.parse_expression()

        if self.check(","):
            expression = self.parse_target_list(
                expression,
                terminators={"=", *self.AUGMENTED_OPERATORS},
            )

        if self.current.value in self.AUGMENTED_OPERATORS:
            self._validate_target(expression, allow_unpacking=False)
            operator = self.advance().value
            value = self.parse_assignment_value()
            return ast.AugmentedAssignment(
                line=line, column=column,
                target=expression, operator=operator, value=value,
            )

        if self.match("="):
            self._validate_target(expression)
            targets = [expression]
            value = self.parse_assignment_value()

            while self.match("="):
                self._validate_target(value)
                targets.append(value)
                value = self.parse_assignment_value()

            return ast.Assignment(
                line=line, column=column,
                targets=targets, value=value,
            )

        return ast.ExpressionStatement(
            line=line, column=column, expression=expression,
        )

    def parse_target_list(self, first, *, terminators: set[str]) -> ast.ASTNode:
        """Parse a bare comma-separated target list using tuple AST nodes."""
        elements = [first]
        while self.match(","):
            if (
                self.current.value in terminators
                or self.current.value in (")", "]", "}", ":", ";",
                )
                or self.current.type in (
                    TokenType.NEWLINE, TokenType.DEDENT, TokenType.EOF,
                )
            ):
                break
            elements.append(self.parse_expression(6))
        return ast.TupleExpression(
            line=first.line,
            column=first.column,
            elements=elements,
        )

    def parse_assignment_value(self) -> ast.ASTNode:
        """Parse an assignment RHS, including an unparenthesized tuple."""
        first = self.parse_expression()
        if not self.check(","):
            return first
        return self.parse_target_list(
            first,
            terminators={"=", *self.AUGMENTED_OPERATORS},
        )

    def _validate_target(
        self,
        target: ast.ASTNode,
        *,
        allow_unpacking: bool = True,
    ) -> None:
        """Reject expressions that cannot be used as binding targets."""
        if isinstance(
            target,
            (ast.Identifier, ast.AttributeAccess, ast.SubscriptExpression),
        ):
            return

        if isinstance(target, ast.StarredExpression):
            raise ParserError("starred target must be inside a list or tuple", self.current)

        if isinstance(target, (ast.TupleExpression, ast.ListExpression)):
            if not allow_unpacking:
                raise ParserError("unpacking is not allowed for this target", self.current)
            starred = sum(
                isinstance(element, ast.StarredExpression)
                for element in target.elements
            )
            if starred > 1:
                raise ParserError("multiple starred targets in one unpacking target", self.current)
            for element in target.elements:
                if isinstance(element, ast.StarredExpression):
                    if not isinstance(
                        element.value,
                        (ast.Identifier, ast.AttributeAccess, ast.SubscriptExpression),
                    ):
                        raise ParserError("invalid starred target", self.current)
                else:
                    self._validate_target(element)
            return

        raise ParserError("invalid assignment target", self.current)

    # ==========================================
    # Compound statements
    # ==========================================

    def parse_suite(self) -> list[ast.ASTNode]:
        self.expect(":")
        if self.check_type(TokenType.NEWLINE):
            self.advance()
            if not self.check_type(TokenType.INDENT):
                raise ParserError("Expected an indented block", self.current)
            self.advance()

            body = []
            self.skip_newlines()

            while (
                not self.check_type(TokenType.DEDENT)
                and not self.check_type(TokenType.EOF)
            ):
                body.extend(self.parse_statement())
                self.skip_newlines()

            self.expect_type(TokenType.DEDENT)
            return body

        return self.parse_simple_statement()

    def parse_if_statement(self) -> ast.IfStatement:
        line, column = self.location()
        test = self.parse_expression()
        body = self.parse_suite()

        elif_branches = []
        else_body = []

        while self.match("elif"):
            condition = self.parse_expression()
            branch_body = self.parse_suite()
            elif_branches.append((condition, branch_body))

        if self.match("else"):
            else_body = self.parse_suite()

        return ast.IfStatement(
            line=line, column=column,
            test=test, body=body,
            elif_branches=elif_branches,
            else_body=else_body,
        )

    def parse_while_statement(self) -> ast.WhileStatement:
        line, column = self.location()
        test = self.parse_expression()
        body = self.parse_suite()
        else_body = []

        if self.match("else"):
            else_body = self.parse_suite()

        return ast.WhileStatement(
            line=line, column=column,
            test=test, body=body, else_body=else_body,
        )

    

    def parse_for_statement(self, is_async: bool = False) -> ast.ForStatement:
        line, column = self.location()

        target = self.parse_expression(6)
        if self.check(","):
            target = self.parse_target_list(target, terminators={"in"})
        self._validate_target(target)
        self.expect("in")

        iterable = self.parse_expression()
        body = self.parse_suite()
        else_body = []

        if self.match("else"):
            else_body = self.parse_suite()

        return ast.ForStatement(
            line=line,
            column=column,
            target=target,
            iterable=iterable,
            body=body,
            else_body=else_body,
            is_async=is_async,
        )


    

    def parse_function_definition(
        self,
        is_async: bool = False,
        decorators: list[ast.ASTNode] | None = None,
    ) -> ast.FunctionDefinition:
        line, column = self.location()
        name = self.expect_type(TokenType.IDENTIFIER).value

        self.expect("(")
        parameters = self.parse_parameters()
        self.expect(")")

        returns = None
        if self.match("->"):
            returns = self.parse_expression()

        previous_async_context = self._in_async_function
        self._in_async_function = is_async
        try:
            body = self.parse_suite()
        finally:
            self._in_async_function = previous_async_context

        return ast.FunctionDefinition(
            line=line,
            column=column,
            name=name,
            parameters=parameters,
            body=body,
            decorators=decorators or [],
            returns=returns,
            is_async=is_async,
        )

    def parse_parameters(self) -> list[ast.Parameter]:
        return self._parse_parameter_list(")", allow_annotations=True)

    def _parse_parameter_list(
        self,
        terminator: str,
        *,
        allow_annotations: bool,
        reject_duplicates: bool = False,
    ) -> list[ast.Parameter]:
        parameters: list[ast.Parameter] = []
        names: set[str] = set()
        positional_count = 0
        positional_default_seen = False
        positional_only_seen = False
        keyword_only_mode = False
        keyword_only_count = 0
        varargs_seen = False
        bare_star_seen = False
        kwargs_seen = False

        while not self.check(terminator) and not self.check_type(TokenType.EOF):
            line, column = self.location()

            if self.match("/"):
                if (
                    positional_only_seen
                    or keyword_only_mode
                    or positional_count == 0
                ):
                    raise ParserError("invalid positional-only marker '/'", self.current)
                positional_only_seen = True
                parameters.append(
                    ast.Parameter(
                        line=line, column=column,
                        name="/", kind="positional_only",
                    )
                )
                if self.match(","):
                    if self.check(terminator):
                        break
                    continue
                break

            if self.match("*"):
                if varargs_seen or keyword_only_mode or kwargs_seen:
                    raise ParserError("invalid '*' parameter", self.current)

                if self.check(","):
                    # A bare '*' marks the start of keyword-only parameters.
                    bare_star_seen = True
                    keyword_only_mode = True
                    self.advance()
                    if self.check(terminator) or self.check("**"):
                        raise ParserError(
                            "a bare '*' must be followed by a keyword-only parameter",
                            self.current,
                        )
                    continue

                kind = "varargs"
                varargs_seen = True
                keyword_only_mode = True
            elif self.match("**"):
                if kwargs_seen:
                    raise ParserError("multiple '**kwargs' parameters", self.current)
                kind = "kwargs"
                kwargs_seen = True
            else:
                kind = "keyword_only" if keyword_only_mode else "normal"

            if not self.check_type(TokenType.IDENTIFIER):
                raise ParserError("Expected parameter name", self.current)
            name = self.advance().value
            if reject_duplicates and name in names:
                raise ParserError(f"duplicate parameter name {name!r}", self.current)
            names.add(name)

            annotation = None
            default = None
            if allow_annotations and self.match(":"):
                annotation = self.parse_expression()

            if self.match("="):
                if kind in ("varargs", "kwargs"):
                    raise ParserError(f"{kind} parameter cannot have a default", self.current)
                default = self.parse_expression()

            if kind == "normal":
                positional_count += 1
                if default is None and positional_default_seen:
                    raise ParserError(
                        "a parameter without a default follows one with a default",
                        self.current,
                    )
                positional_default_seen = positional_default_seen or default is not None
            elif kind == "keyword_only":
                keyword_only_count += 1

            parameters.append(
                ast.Parameter(
                    line=line, column=column, name=name, kind=kind,
                    default=default, annotation=annotation,
                )
            )

            if kind == "kwargs":
                if self.match(",") and not self.check(terminator):
                    raise ParserError("no parameter may follow '**kwargs'", self.current)
                break

            if not self.match(","):
                break

        if bare_star_seen and keyword_only_count == 0:
            raise ParserError(
                "a bare '*' must be followed by a keyword-only parameter",
                self.current,
            )
        return parameters

    def parse_class_definition(
        self, decorators: list[ast.ASTNode] | None = None,
    ) -> ast.ClassDefinition:
        line, column = self.location()
        name = self.expect_type(TokenType.IDENTIFIER).value
        bases = []

        if self.match("("):
            if not self.check(")"):
                bases = self.parse_expression_list()
            self.expect(")")

        previous_async_context = self._in_async_function
        self._in_async_function = False
        try:
            body = self.parse_suite()
        finally:
            self._in_async_function = previous_async_context

        return ast.ClassDefinition(
            line=line, column=column,
            name=name, bases=bases,
            body=body, decorators=decorators or [],
        )

    def parse_decorated_definition(self) -> ast.ASTNode:
        decorators = []

        while self.match("@"):
            decorators.append(self.parse_expression())
            if self.check_type(TokenType.NEWLINE):
                self.advance()
            else:
                raise ParserError("Expected newline after decorator", self.current)

        if self.match("async"):
            self.expect("def")
            return self.parse_function_definition(
                is_async=True, decorators=decorators,
            )

        if self.match("def"):
            return self.parse_function_definition(decorators=decorators)

        if self.match("class"):
            return self.parse_class_definition(decorators=decorators)

        raise ParserError("Expected function or class after decorators", self.current)

    def parse_try_statement(self) -> ast.TryStatement:
        line, column = self.location()
        body = self.parse_suite()
        handlers = []
        else_body = []
        finally_body = []
        handler_kind = None

        while self.match("except"):
            handler_line, handler_column = self.location()
            is_star = self.match("*")
            current_kind = "except*" if is_star else "except"
            if handler_kind is not None and current_kind != handler_kind:
                raise ParserError(
                    "cannot mix 'except' and 'except*' handlers", self.current,
                )
            handler_kind = current_kind

            exception = None
            name = None

            if not self.check(":"):
                exception = self.parse_expression()
                if self.match("as"):
                    name = self.expect_type(TokenType.IDENTIFIER).value
            elif is_star:
                raise ParserError("'except*' requires an exception type", self.current)

            handler_body = self.parse_suite()
            handlers.append(
                ast.ExceptHandler(
                    line=handler_line, column=handler_column,
                    exception=exception, name=name, body=handler_body,
                    is_star=is_star,
                )
            )

        if self.match("else"):
            else_body = self.parse_suite()

        if self.match("finally"):
            finally_body = self.parse_suite()

        if not handlers and not finally_body:
            raise ParserError("try requires except or finally", self.current)

        return ast.TryStatement(
            line=line, column=column,
            body=body, handlers=handlers,
            else_body=else_body, finally_body=finally_body,
        )

    def parse_with_statement(self, is_async: bool = False) -> ast.WithStatement:
        line, column = self.location()
        items = []

        if self.check("("):
            opening = self.advance()
            trailing_comma = False
            if self.match(")"):
                # An empty tuple is a valid context expression: ``with ()``.
                items.append((
                    ast.TupleExpression(
                        line=opening.line,
                        column=opening.column,
                        elements=[],
                    ),
                    None,
                ))
            else:
                while True:
                    context = self.parse_expression()
                    target = None

                    if self.match("as"):
                        target = self.parse_expression()

                    items.append((context, target))

                    if not self.match(","):
                        break
                    if self.check(")"):
                        trailing_comma = True
                        break

                self.expect(")")

            if self.match("as"):
                if any(target is not None for _context, target in items):
                    raise ParserError(
                        "a parenthesized context expression cannot contain "
                        "'as' items when followed by an outer 'as'",
                        self.current,
                    )
                if len(items) == 1 and not trailing_comma:
                    context = items[0][0]
                else:
                    context = ast.TupleExpression(
                        line=opening.line,
                        column=opening.column,
                        elements=[item for item, _target in items],
                    )
                target = self.parse_expression()
                items = [(context, target)]
        else:
            while True:
                context = self.parse_expression()
                target = None

                if self.match("as"):
                    target = self.parse_expression()

                items.append((context, target))

                if not self.match(","):
                    break

        body = self.parse_suite()

        return ast.WithStatement(
            line=line, column=column,
            items=items, body=body, is_async=is_async,
        )

    # ==========================================
    # Imports
    # ==========================================

    def parse_import_statement(self, line: int, column: int) -> ast.ASTNode:
        statements = []

        while True:
            module = self.expect_type(TokenType.IDENTIFIER).value

            while self.match("."):
                module += "." + self.expect_type(TokenType.IDENTIFIER).value

            alias = None
            if self.match("as"):
                alias = self.expect_type(TokenType.IDENTIFIER).value

            statements.append(
                ast.ImportStatement(
                    line=line, column=column,
                    module=module, alias=alias,
                )
            )

            if not self.match(","):
                break

        if len(statements) == 1:
            return statements[0]

        return ast.ExpressionStatement(
            line=line, column=column,
            expression=ast.TupleExpression(
                line=line, column=column, elements=statements,
            ),
        )

    def parse_import_from_statement(self, line: int, column: int) -> ast.ImportFromStatement:
        level = 0
        module = ""

        while self.match("."):
            level += 1

        if self.check_type(TokenType.IDENTIFIER):
            module = self.advance().value
            while self.match("."):
                module += "." + self.expect_type(TokenType.IDENTIFIER).value

        self.expect("import")

        names = []
        parenthesized = self.match("(")

        while True:
            name = self.expect_type(TokenType.IDENTIFIER).value
            alias = None

            if self.match("as"):
                alias = self.expect_type(TokenType.IDENTIFIER).value

            names.append((name, alias))

            if not self.match(","):
                break

            if parenthesized and self.check(")"):
                break

        if parenthesized:
            self.expect(")")

        return ast.ImportFromStatement(
            line=line, column=column,
            module=module, names=names, level=level,
        )

    # ==========================================
    # Expressions: Pratt parser
    # ==========================================

    def parse_expression(self, min_precedence: int = 1) -> ast.ASTNode:
        left = self.parse_prefix()

        while True:
            token = self.current
            operator = token.value

            # Postfix operations have the highest precedence.
            if operator == "(":
                left = self.parse_call(left)
                continue

            if operator == ".":
                self.advance()
                attribute = self.expect_type(TokenType.IDENTIFIER).value
                left = ast.AttributeAccess(
                    line=token.line, column=token.column,
                    object=left, attribute=attribute,
                )
                continue

            if operator == "[":
                left = self.parse_subscript(left)
                continue

            # Conditional expression: a if condition else b
            if operator == "if" and min_precedence <= 1:
                self.advance()
                condition = self.parse_expression(2)
                self.expect("else")
                alternative = self.parse_expression(1)
                left = ast.ConditionalExpression(
                    line=token.line, column=token.column,
                    value=left, condition=condition,
                    alternative=alternative,
                )
                continue

            # Comparison operators can be chained.
            if operator in self.COMPARISON_OPERATORS or (
                operator == "not" and self.peek().value == "in"
            ) or (operator == "is" and self.peek().value == "not"):
                precedence = 5
                if precedence < min_precedence:
                    break

                operators = []
                comparators = []

                while True:
                    if self.match("not"):
                        self.expect("in")
                        current_operator = "not in"
                    elif self.match("is"):
                        current_operator = "is not" if self.match("not") else "is"
                    else:
                        current_operator = self.advance().value

                    operators.append(current_operator)
                    comparators.append(self.parse_expression(precedence + 1))

                    if self.current.value not in self.COMPARISON_OPERATORS and not (
                        self.current.value == "not" and self.peek().value == "in"
                    ):
                        break

                left = ast.Comparison(
                    line=token.line, column=token.column,
                    left=left, operators=operators,
                    comparators=comparators,
                )
                continue

            precedence = self.PRECEDENCE.get(operator, 0)
            if precedence == 0 or precedence < min_precedence:
                break

            self.advance()

            # Exponentiation and assignment expressions associate right.
            next_min = precedence if operator in ("**", ":=") else precedence + 1
            right = self.parse_expression(next_min)

            if operator == ":=":
                left = ast.NamedExpression(
                    line=token.line, column=token.column,
                    target=left, value=right,
                )
            elif operator in ("and", "or"):
                left = ast.BooleanOperation(
                    line=token.line, column=token.column,
                    left=left, operator=operator, right=right,
                )
            else:
                left = ast.BinaryOperation(
                    line=token.line, column=token.column,
                    left=left, operator=operator, right=right,
                )

        return left

    def parse_prefix(self) -> ast.ASTNode:
        token = self.current
        line, column = token.line, token.column
        value = token.value

        if self.match("not", "+", "-", "~"):
            operand = self.parse_expression(4 if value == "not" else 13)
            return ast.UnaryOperation(
                line=line, column=column,
                operator=value, operand=operand,
            )

        if self.match("await"):
            return ast.AwaitExpression(
                line=line, column=column,
                expression=self.parse_expression(13),
            )

        if self.match("yield"):
            is_from = self.match("from")
            result = None
            if not self.check_type(TokenType.NEWLINE) and not self.check(")") and not self.check(","):
                result = self.parse_expression()
            return ast.YieldExpression(
                line=line, column=column, value=result, is_from=is_from,
            )

        if self.match("lambda"):
            parameters = self.parse_parameters_until_colon()
            self.expect(":")
            previous_async_context = self._in_async_function
            self._in_async_function = False
            try:
                body = self.parse_expression()
            finally:
                self._in_async_function = previous_async_context
            return ast.LambdaExpression(
                line=line, column=column,
                parameters=parameters, body=body,
            )

        if self.match("*"):
            return ast.StarredExpression(
                line=line, column=column,
                value=self.parse_expression(13),
            )

        if self.match("("):
            if self.match(")"):
                return ast.TupleExpression(line=line, column=column, elements=[])

            expression = self.parse_expression()

            if self._starts_comprehension():
                generators = self.parse_comprehensions()
                self.expect(")")
                return ast.GeneratorExpression(
                    line=line, column=column,
                    element=expression, generators=generators,
                )

            if self.match(","):
                elements = [expression]
                while not self.check(")") and not self.check_type(TokenType.EOF):
                    elements.append(self.parse_expression())
                    if not self.match(","):
                        break
                self.expect(")")
                return ast.TupleExpression(
                    line=line, column=column, elements=elements,
                )

            self.expect(")")
            return expression

        if self.match("["):
            return self.parse_list_expression(line, column)

        if self.match("{"):
            return self.parse_brace_expression(line, column)

        if token.type == TokenType.IDENTIFIER:
            self.advance()
            return ast.Identifier(
                line=line, column=column, name=value,
            )

        if token.type in (TokenType.INTEGER, TokenType.FLOAT):
            self.advance()
            try:
                number = value.replace("_", "")
                if number.lower().startswith(("0x", "0o", "0b")):
                    parsed_value = int(number, 0)
                elif token.type == TokenType.INTEGER:
                    parsed_value = int(number)
                else:
                    parsed_value = float(number)
            except ValueError:
                parsed_value = value

            return ast.Literal(
                line=line, column=column, value=parsed_value,
            )

        if token.type == TokenType.STRING:
            self.advance()
            if value.lower() in ("true", "false", "none"):
                literal_value = {
                    "true": True, "false": False, "none": None,
                }[value.lower()]
                return ast.Literal(
                    line=line, column=column, value=literal_value,
                )

            if self._is_fstring_literal(value):
                return self._parse_fstring(token, value)

            return ast.Literal(
                line=line, column=column, value=value,
            )

        if value in ("True", "False", "None"):
            self.advance()
            literal_value = {
                "True": True, "False": False, "None": None,
            }[value]
            return ast.Literal(
                line=line, column=column, value=literal_value,
            )

        raise ParserError("Expected expression", token)

    @staticmethod
    def _is_fstring_literal(value: str) -> bool:
        prefix_end = 0
        while prefix_end < len(value) and value[prefix_end].isalpha():
            prefix_end += 1
        return "f" in value[:prefix_end].lower()

    def _parse_fstring(self, token: Token, value: str) -> ast.FStringExpression:
        prefix_end = 0
        while prefix_end < len(value) and value[prefix_end].isalpha():
            prefix_end += 1
        quote_index = prefix_end
        quote = value[quote_index]
        delimiter = quote * 3 if value.startswith(quote * 3, quote_index) else quote
        body = value[quote_index + len(delimiter):-len(delimiter)]
        return ast.FStringExpression(
            line=token.line,
            column=token.column,
            value=value,
            parts=self._parse_fstring_parts(body, token.line, token.column),
        )

    def _parse_fstring_parts(
        self,
        content: str,
        line: int,
        column: int,
    ) -> list[ast.ASTNode]:
        parts: list[ast.ASTNode] = []
        text: list[str] = []
        index = 0

        def flush_text() -> None:
            if text:
                parts.append(ast.FStringText(line=line, column=column, value="".join(text)))
                text.clear()

        while index < len(content):
            if content.startswith("{{", index):
                text.append("{")
                index += 2
                continue
            if content.startswith("}}", index):
                text.append("}")
                index += 2
                continue
            if content[index] == "}":
                raise ParserError("single '}' is not allowed in an f-string")
            if content[index] != "{":
                text.append(content[index])
                index += 1
                continue

            flush_text()
            closing = self._find_fstring_field_end(content, index + 1)
            if closing is None:
                raise ParserError("expected '}' to close f-string field")
            parts.append(
                self._parse_fstring_field(content[index + 1:closing], line, column)
            )
            index = closing + 1

        flush_text()
        return parts

    @staticmethod
    def _find_fstring_field_end(content: str, start: int) -> int | None:
        brackets: list[str] = []
        index = start

        while index < len(content):
            char = content[index]
            if char in "'\"":
                quote = char
                delimiter = quote * 3 if content.startswith(quote * 3, index) else quote
                index += len(delimiter)
                while index < len(content):
                    if content.startswith(delimiter, index):
                        index += len(delimiter)
                        break
                    if content[index] == "\\":
                        index += 2
                    else:
                        index += 1
                continue
            if char == "#":
                newline = content.find("\n", index)
                index = len(content) if newline < 0 else newline + 1
                continue
            if char in "([{":
                brackets.append({"(": ")", "[": "]", "{": "}"}[char])
            elif char in ")]}":
                if brackets and char == brackets[-1]:
                    brackets.pop()
                elif char == "}" and not brackets:
                    return index
            index += 1

        return None

    def _parse_fstring_field(
        self,
        content: str,
        line: int,
        column: int,
    ) -> ast.FStringField:
        expression_end = len(content)
        conversion = None
        format_text = ""
        debug_text = None
        brackets: list[str] = []
        index = 0
        delimiter_kind = None

        while index < len(content):
            char = content[index]
            if char in "'\"":
                quote = char
                delimiter = quote * 3 if content.startswith(quote * 3, index) else quote
                index += len(delimiter)
                while index < len(content):
                    if content.startswith(delimiter, index):
                        index += len(delimiter)
                        break
                    if content[index] == "\\":
                        index += 2
                    else:
                        index += 1
                continue
            if char in "([{":
                brackets.append({"(": ")", "[": "]", "{": "}"}[char])
                index += 1
                continue
            if char in ")]}":
                if brackets and char == brackets[-1]:
                    brackets.pop()
                index += 1
                continue
            if not brackets:
                if char == "!" and not content.startswith("!=", index):
                    expression_end = index
                    delimiter_kind = "conversion"
                    break
                if char == ":" and not content.startswith(":=", index):
                    expression_end = index
                    delimiter_kind = "format"
                    break
                if char == "=" and not (
                    content.startswith(("==", "!=", "<=", ">=", ":="), index)
                    or (index > 0 and content[index - 1] in "=!<>:")
                ):
                    expression_end = index
                    debug_text = content[:index + 1]
                    index += 1
                    delimiter_kind = "debug"
                    break
            index += 1

        expression_text = content[:expression_end].strip()
        if not expression_text:
            raise ParserError("empty expression in f-string field")

        if delimiter_kind == "conversion":
            conversion_index = index + 1
            if conversion_index >= len(content) or content[conversion_index] not in "rsa":
                raise ParserError("invalid f-string conversion; expected !s, !r, or !a")
            conversion = content[conversion_index]
            index = conversion_index + 1
            if index < len(content):
                if content[index] != ":":
                    raise ParserError("unexpected text after f-string conversion")
                format_text = content[index + 1:]
        elif delimiter_kind == "format":
            format_text = content[index + 1:]
        elif delimiter_kind == "debug":
            while index < len(content) and content[index].isspace():
                index += 1
            debug_text = content[:index]
            if index < len(content) and content[index] == "!":
                if index + 1 >= len(content) or content[index + 1] not in "rsa":
                    raise ParserError("invalid f-string conversion; expected !s, !r, or !a")
                conversion = content[index + 1]
                index += 2
                while index < len(content) and content[index].isspace():
                    index += 1
            if index < len(content):
                if content[index] != ":":
                    raise ParserError("unexpected text after f-string debug expression")
                format_text = content[index + 1:]

        expression_tokens = Lexer(expression_text).tokenize()
        expression_parser = Parser(expression_tokens)
        expression = expression_parser.parse_expression()
        if not expression_parser.check_type(TokenType.EOF):
            raise ParserError("unexpected text in f-string expression", expression_parser.current)

        return ast.FStringField(
            line=line,
            column=column,
            expression=expression,
            conversion=conversion,
            format_spec=self._parse_fstring_parts(format_text, line, column)
            if format_text else [],
            debug_text=debug_text,
        )

    # ==========================================
    # Expression helpers
    # ==========================================

    def parse_parameters_until_colon(self) -> list[ast.Parameter]:
        return self._parse_parameter_list(
            ":", allow_annotations=False, reject_duplicates=True,
        )

    def parse_expression_list(self) -> list[ast.ASTNode]:
        expressions = [self.parse_expression()]

        while self.match(","):
            if self.check(")") or self.check("]") or self.check("}"):
                break
            expressions.append(self.parse_expression())

        return expressions

    def parse_call(self, function: ast.ASTNode) -> ast.CallExpression:
        token = self.expect("(")
        arguments = []

        while not self.check(")") and not self.check_type(TokenType.EOF):
            line, column = self.location()
            keyword_argument = False

            if self.match("**"):
                value = self.parse_expression()
                arguments.append(
                    ast.StarredExpression(
                        line=line, column=column, value=value,
                    )
                )
            elif self.match("*"):
                value = self.parse_expression()
                arguments.append(
                    ast.StarredExpression(
                        line=line, column=column, value=value,
                    )
                )
            elif (
                self.check_type(TokenType.IDENTIFIER)
                and self.peek().value == "="
            ):
                name = self.advance().value
                self.advance()
                value = self.parse_expression()
                keyword_argument = True
                arguments.append(
                    ast.KeywordArgument(
                        line=line, column=column,
                        name=name, value=value,
                    )
                )
            else:
                argument = self.parse_expression()
                if self._starts_comprehension():
                    if arguments or keyword_argument:
                        raise ParserError(
                            "an unparenthesized generator expression must be "
                            "the only call argument",
                            self.current,
                        )
                    generators = self.parse_comprehensions()
                    argument = ast.GeneratorExpression(
                        line=argument.line,
                        column=argument.column,
                        element=argument,
                        generators=generators,
                    )
                    if self.check(","):
                        raise ParserError(
                            "an unparenthesized generator expression cannot "
                            "have a trailing comma",
                            self.current,
                        )
                arguments.append(argument)

            if keyword_argument and self._starts_comprehension():
                raise ParserError(
                    "an unparenthesized generator expression cannot be a "
                    "keyword argument",
                    self.current,
                )

            if not self.match(","):
                break

        self.expect(")")

        return ast.CallExpression(
            line=token.line, column=token.column,
            function=function, arguments=arguments,
        )

    def parse_subscript(self, value: ast.ASTNode) -> ast.SubscriptExpression:
        token = self.expect("[")
        start = None
        stop = None
        step = None

        if not self.check(":"):
            start = self.parse_expression()

        if self.match(":"):
            if not self.check("]") and not self.check(":"):
                stop = self.parse_expression()

            if self.match(":"):
                if not self.check("]"):
                    step = self.parse_expression()

            index = ast.SliceExpression(
                line=token.line, column=token.column,
                start=start, stop=stop, step=step,
            )
        else:
            index = start

        self.expect("]")

        return ast.SubscriptExpression(
            line=token.line, column=token.column,
            value=value, index=index,
        )

    def parse_list_expression(self, line: int, column: int) -> ast.ASTNode:
        if self.match("]"):
            return ast.ListExpression(
                line=line, column=column, elements=[],
            )

        first = self.parse_expression()

        if self._starts_comprehension():
            generators = self.parse_comprehensions()
            self.expect("]")
            return ast.ListComprehension(
                line=line, column=column,
                element=first, generators=generators,
            )

        elements = [first]

        while self.match(","):
            if self.check("]"):
                break
            elements.append(self.parse_expression())

        self.expect("]")

        return ast.ListExpression(
            line=line, column=column, elements=elements,
        )

    def _starts_comprehension(self) -> bool:
        return self.check("for") or (
            self.check("async") and self.peek().value == "for"
        )

    def parse_comprehensions(self) -> list[ast.Comprehension]:
        """Parse one or more ``for`` clauses, each with its own filters."""
        generators = []

        while self._starts_comprehension():
            line, column = self.location()
            is_async = self.match("async")
            if is_async and not self._in_async_function:
                raise ParserError(
                    "asynchronous comprehensions are only allowed in an "
                    "async function",
                    self.current,
                )
            self.expect("for")
            target = self.parse_expression(6)
            if self.check(","):
                target = self.parse_target_list(target, terminators={"in"})
            self._validate_target(target)
            self.expect("in")
            iterable = self.parse_expression(2)

            conditions = []
            while self.match("if"):
                conditions.append(self.parse_expression(2))

            generators.append(
                ast.Comprehension(
                    line=line, column=column,
                    target=target, iterable=iterable,
                    conditions=conditions, is_async=is_async,
                )
            )

        return generators

    def parse_brace_expression(self, line: int, column: int) -> ast.ASTNode:
        if self.match("}"):
            return ast.DictionaryExpression(
                line=line, column=column, entries=[],
            )

        first = self.parse_expression()

        if self.match(":"):
            first_value = self.parse_expression()
            if self._starts_comprehension():
                generators = self.parse_comprehensions()
                self.expect("}")
                return ast.DictionaryComprehension(
                    line=line, column=column,
                    element=first_value, generators=generators,
                    key=first,
                )
            entries = [(first, first_value)]

            while self.match(","):
                if self.check("}"):
                    break
                key = self.parse_expression()
                self.expect(":")
                value = self.parse_expression()
                entries.append((key, value))

            self.expect("}")
            return ast.DictionaryExpression(
                line=line, column=column, entries=entries,
            )

        if self._starts_comprehension():
            generators = self.parse_comprehensions()
            self.expect("}")
            return ast.SetComprehension(
                line=line, column=column,
                element=first, generators=generators,
            )

        elements = [first]

        while self.match(","):
            if self.check("}"):
                break
            elements.append(self.parse_expression())

        self.expect("}")

        return ast.SetExpression(
            line=line, column=column, elements=elements,
        )
