"""Base types shared by every lint rule, in every language.

A :class:`Rule` is a small, self-contained check: given a
:class:`RuleContext` (the parsed tree, its source text, and a place to
cache expensive analysis), it returns zero or more
:class:`~polylint.core.diagnostics.Diagnostic` objects.

Nothing here is Python-specific. The :func:`walk` helper recurses
through *any* tree of dataclass instances (lists and tuples included)
purely by introspecting ``dataclasses.fields`` -- it doesn't know or
care what language's AST it's looking at, which lets every future
language's rules reuse it unchanged.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, Hashable, Iterator, Optional

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity


def walk(node: Any) -> Iterator[Any]:
    """Yield ``node`` and every dataclass instance reachable from it,
    depth-first, pre-order, descending through lists and tuples (so
    fields like ``list[tuple[ASTNode, ASTNode | None]]`` are handled
    without any language-specific knowledge)."""
    if node is None:
        return
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in dataclasses.fields(node):
            yield from walk(getattr(node, f.name))
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from walk(item)
    # Anything else (str, int, bool, None, enum members, ...) is a leaf.


class RuleContext:
    """Everything a rule needs to check one file, plus a small cache so
    multiple rules that depend on the same expensive analysis (e.g. the
    semantic analyzer) only pay for it once per run."""

    def __init__(self, tree: Any, source: str, file_path: str = "<module>") -> None:
        self.tree = tree
        self.source = source
        self.file_path = file_path
        self._cache: dict[Hashable, Any] = {}

    @property
    def lines(self) -> list[str]:
        if "lines" not in self._cache:
            self._cache["lines"] = self.source.splitlines()
        return self._cache["lines"]

    def cached(self, key: Hashable, compute: Callable[[], Any]) -> Any:
        """Return ``compute()``'s result, computing it at most once per
        context and reusing it for every rule that asks for the same
        ``key`` afterwards."""
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]


class Rule(ABC):
    """Base class for a single lint rule.

    Subclasses set the class-level metadata (``id``, ``name``,
    ``description``, ``category``, ``default_severity``) and implement
    :meth:`check`. An instance additionally carries whatever severity
    and enabled/disabled state the user's configuration gave it --
    :attr:`severity` defaults to ``default_severity`` and may be
    overridden per instance without touching the class.
    """

    id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    category: ClassVar[str] = "general"
    default_severity: ClassVar[Severity] = Severity.WARNING

    def __init__(self, severity: Optional[Severity] = None, enabled: bool = True) -> None:
        self.severity = severity if severity is not None else self.default_severity
        self.enabled = enabled

    @abstractmethod
    def check(self, context: RuleContext) -> list[Diagnostic]:
        """Return the diagnostics this rule finds in ``context``."""
        raise NotImplementedError

    def diagnostic(self, message: str, line: int, column: int, **kwargs: Any) -> Diagnostic:
        """Convenience constructor: fills in this rule's id and current
        severity, leaving only the message and location to supply."""
        return Diagnostic(
            rule_id=self.id,
            message=message,
            line=line,
            column=column,
            severity=self.severity,
            **kwargs,
        )

    def diagnostic_for(self, message: str, node: Any, **kwargs: Any) -> Diagnostic:
        """Like :meth:`diagnostic`, but takes the location from an AST
        node's ``.line``/``.column`` attributes."""
        return self.diagnostic(message, node.line, node.column, **kwargs)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Rule {self.id} ({self.category}) severity={self.severity}>"