from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class SymbolKind(Enum):
    VARIABLE = auto()
    PARAMETER = auto()
    FUNCTION = auto()
    CLASS = auto()
    IMPORT = auto()
    EXCEPTION = auto()


@dataclass
class Symbol:
    """One name binding in a scope."""

    name: str
    kind: SymbolKind
    line: int = 0
    column: int = 0
    node: Any = None
    used: bool = False

    # How many times (re)assigned in its own scope. Useful for shadowing
    # / redefinition checks.
    assignment_count: int = field(default=0, repr=False)


class SymbolTable:
    """A flat, ordered mapping of names to :class:`Symbol` objects."""

    def __init__(self) -> None:
        self._symbols: dict[str, Symbol] = {}

    def define(self, symbol: Symbol) -> Symbol:
        existing = self._symbols.get(symbol.name)
        if existing is not None:
            # Preserve "used" status across redefinitions, but track how
            # many times the name has been (re)bound in this scope.
            symbol.used = symbol.used or existing.used
            symbol.assignment_count = existing.assignment_count + 1
        self._symbols[symbol.name] = symbol
        return symbol

    def get(self, name: str) -> Optional[Symbol]:
        return self._symbols.get(name)

    def contains(self, name: str) -> bool:
        return name in self._symbols

    def all(self) -> list[Symbol]:
        return list(self._symbols.values())

    def __iter__(self):
        return iter(self._symbols.values())

    def __len__(self) -> int:
        return len(self._symbols)

    def __contains__(self, name: str) -> bool:
        return name in self._symbols