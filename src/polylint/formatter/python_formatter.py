
from __future__ import annotations

import io
import tokenize
from dataclasses import dataclass


@dataclass
class FormatterConfig:
    indent_size: int = 4
    max_line_length: int = 88
    final_newline: bool = True
    remove_trailing_whitespace: bool = True


class PythonFormatter:
    """Basic token-aware Python source formatter."""

    def __init__(self, config: FormatterConfig | None = None):
        self.config = config or FormatterConfig()

        if self.config.indent_size < 1:
            raise ValueError("indent_size must be positive")

        if self.config.max_line_length < 1:
            raise ValueError("max_line_length must be positive")

    def format_code(self, source: str) -> str:
        if not source:
            return "\n" if self.config.final_newline else ""

        try:
            tokens = list(
                tokenize.generate_tokens(
                    io.StringIO(source).readline
                )
            )
        except (tokenize.TokenError, IndentationError):
            return self._finish(source)

        result = self._format_tokens(tokens)
        return self._finish(result)

    def _format_tokens(
        self,
        tokens: list[tokenize.TokenInfo],
    ) -> str:
        result: list[str] = []
        previous = None
        indent_level = 0
        line_start = True

        for token in tokens:
            token_type = token.type
            value = token.string

            if token_type in (
                tokenize.ENDMARKER,
                tokenize.ENCODING,
            ):
                continue

            if token_type == tokenize.INDENT:
                indent_level += 1
                continue

            if token_type == tokenize.DEDENT:
                indent_level = max(0, indent_level - 1)
                continue

            if token_type == tokenize.NEWLINE:
                self._remove_trailing_spaces(result)
                result.append("\n")
                line_start = True
                previous = None
                continue

            if token_type == tokenize.NL:
                self._remove_trailing_spaces(result)
                result.append("\n")
                line_start = True
                previous = None
                continue

            if token_type == tokenize.COMMENT:
                if line_start:
                    result.append(
                        " " * (
                            indent_level * self.config.indent_size
                        )
                    )
                    line_start = False
                elif result and result[-1] not in (" ", "\n"):
                    result.append(" ")

                result.append(value)
                previous = token
                continue

            if line_start:
                result.append(
                    " " * (
                        indent_level * self.config.indent_size
                    )
                )
                line_start = False

            if self._needs_space(previous, token):
                if result and result[-1] not in (" ", "\n"):
                    result.append(" ")

            result.append(value)
            previous = token

        return "".join(result)

    @staticmethod
    def _remove_trailing_spaces(result: list[str]) -> None:
        while result and result[-1] == " ":
            result.pop()

    @staticmethod
    def _needs_space(
        previous: tokenize.TokenInfo | None,
        current: tokenize.TokenInfo,
    ) -> bool:
        if previous is None:
            return False

        prev_value = previous.string
        curr_value = current.string

        # No space before closing brackets or punctuation.
        if current.type == tokenize.OP:
            if curr_value in (")", "]", "}", ",", ";", ".", ":"):
                return False

            # Opening brackets: space after operators,
            # but not after function names or identifiers.
            if curr_value in ("(", "[", "{"):
                return (
                    previous.type == tokenize.OP
                    and prev_value not in ("(", "[", "{", ".")
                )

            # Binary operators.
            return True

        # No space immediately after opening brackets or dot.
        if previous.type == tokenize.OP:
            if prev_value in ("(", "[", "{", "."):
                return False

            # Space after commas and operators.
            return True

        # Adjacent names, numbers and strings need separation.
        if (
            previous.type in (
                tokenize.NAME,
                tokenize.NUMBER,
                tokenize.STRING,
            )
            and current.type in (
                tokenize.NAME,
                tokenize.NUMBER,
                tokenize.STRING,
            )
        ):
            return True

        return True

    def _finish(self, source: str) -> str:
        if self.config.remove_trailing_whitespace:
            source = "\n".join(
                line.rstrip() for line in source.splitlines()
            )

        source = source.rstrip("\n")

        if self.config.final_newline:
            return source + "\n"

        return source
