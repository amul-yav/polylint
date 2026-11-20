from __future__ import annotations

from enum import Enum, auto
from typing import Iterator, Optional

from polylint.languages.python.symbols import Symbol, SymbolKind, SymbolTable


class ScopeKind(Enum):
    MODULE = auto()
    FUNCTION = auto()
    CLASS = auto()
    LAMBDA = auto()
    COMPREHENSION = auto()


class Scope:
    def __init__(
        self,
        kind: ScopeKind,
        parent: Optional["Scope"] = None,
        name: str = "",
    ) -> None:
        self.kind = kind
        self.parent = parent
        self.name = name
        self.symbols = SymbolTable()
        self.children: list["Scope"] = []

        # Names declared `global` / `nonlocal` inside this scope.
        self.globals: set[str] = set()
        self.nonlocals: set[str] = set()

        if parent is not None:
            parent.children.append(self)

    # ------------------------------------------------------------
    # Declaration
    # ------------------------------------------------------------

    def declare(
        self,
        name: str,
        kind: SymbolKind,
        line: int = 0,
        column: int = 0,
        node=None,
    ) -> Symbol:
        symbol = Symbol(name=name, kind=kind, line=line, column=column, node=node)
        return self.symbols.define(symbol)

    def declare_global(self, name: str) -> None:
        self.globals.add(name)

    def declare_nonlocal(self, name: str) -> None:
        self.nonlocals.add(name)

    # ------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------

    def is_module_scope(self) -> bool:
        return self.kind == ScopeKind.MODULE

    def module_scope(self) -> "Scope":
        scope = self
        while scope.parent is not None:
            scope = scope.parent
        return scope

    def nearest_enclosing_function(self) -> Optional["Scope"]:
        """The nearest ancestor FUNCTION/LAMBDA scope (skipping CLASS),
        used as the binding site for ``nonlocal`` declarations."""
        scope = self.parent
        while scope is not None:
            if scope.kind in (ScopeKind.FUNCTION, ScopeKind.LAMBDA):
                return scope
            scope = scope.parent
        return None

    def enclosing_lookup_scopes(self) -> Iterator["Scope"]:
        """Ancestor scopes consulted during LEGB lookup, in order,
        skipping CLASS scopes (a nested function cannot see the
        enclosing class body's names implicitly)."""
        scope = self.parent
        while scope is not None:
            if scope.kind != ScopeKind.CLASS:
                yield scope
            scope = scope.parent

    def resolve_local(self, name: str) -> Optional[Symbol]:
        """Look up ``name`` only within this scope's own table."""
        return self.symbols.get(name)

    def resolve(self, name: str) -> Optional[Symbol]:
        """Resolve ``name`` per Python's LEGB rule, honouring any
        ``global``/``nonlocal`` declaration made in *this* scope."""
        if name in self.globals:
            return self.module_scope().symbols.get(name)

        if name in self.nonlocals:
            for scope in self.enclosing_lookup_scopes():
                if scope.kind in (ScopeKind.FUNCTION, ScopeKind.LAMBDA):
                    symbol = scope.symbols.get(name)
                    if symbol is not None:
                        return symbol
            return None

        if self.symbols.contains(name):
            return self.symbols.get(name)

        for scope in self.enclosing_lookup_scopes():
            symbol = scope.symbols.get(name)
            if symbol is not None:
                return symbol

        return None