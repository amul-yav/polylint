
"""Base types shared by every lint rule."""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, Hashable, Iterator, Optional

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity
from polylint.fix.fixer import Fix


def walk(node: Any) -> Iterator[Any]:
    """Walk through dataclass AST nodes recursively."""
    if node is None:
        return

    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        yield node
        for field in dataclasses.fields(node):
            yield from walk(getattr(node, field.name))

    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from walk(item)


class RuleContext:
    """Context shared by rules during one analysis run."""

    def __init__(
        self,
        tree: Any,
        source: str,
        file_path: str = "<module>",
    ) -> None:
        self.tree = tree
        self.source = source
        self.file_path = file_path
        self._cache: dict[Hashable, Any] = {}
        self.fixes: list[Fix] = []

    @property
    def lines(self) -> list[str]:
        if "lines" not in self._cache:
            self._cache["lines"] = self.source.splitlines()
        return self._cache["lines"]

    def cached(
        self,
        key: Hashable,
        compute: Callable[[], Any],
    ) -> Any:
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    def add_fix(self, fix: Fix) -> None:
        """Register an automatic fix produced by a rule."""
        self.fixes.append(fix)


class Rule(ABC):
    """Base class for a single lint rule."""

    id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    category: ClassVar[str] = "general"
    default_severity: ClassVar[Severity] = Severity.WARNING

    def __init__(
        self,
        severity: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        self.severity = (
            severity if severity is not None else self.default_severity
        )
        self.enabled = enabled

    @abstractmethod
    def check(self, context: RuleContext) -> list[Diagnostic]:
        raise NotImplementedError

    def diagnostic(
        self,
        message: str,
        line: int,
        column: int,
        **kwargs: Any,
    ) -> Diagnostic:
        return Diagnostic(
            rule_id=self.id,
            message=message,
            line=line,
            column=column,
            severity=self.severity,
            **kwargs,
        )

    def diagnostic_for(
        self,
        message: str,
        node: Any,
        **kwargs: Any,
    ) -> Diagnostic:
        return self.diagnostic(
            message,
            node.line,
            node.column,
            **kwargs,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id!r})"
