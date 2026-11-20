from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    IDENTIFIER = auto()
    KEYWORD = auto()

    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()

    OPERATOR = auto()
    PUNCTUATION = auto()

    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int