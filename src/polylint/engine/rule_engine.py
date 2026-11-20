"""Coordinates parsing's output with the rule registry: build one
:class:`~polylint.rules.base.RuleContext` per file and run every
enabled rule against it.
"""

from __future__ import annotations

from typing import Iterable, Optional

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity

# Importing this registers every built-in Python rule as a side effect.
import polylint.rules.python  # noqa: F401

from polylint.rules.base import Rule, RuleContext
from polylint.rules.registry import RuleRegistry, default_registry


class RuleEngine:
    def __init__(
        self,
        registry: Optional[RuleRegistry] = None,
        *,
        enabled_ids: Optional[Iterable[str]] = None,
        disabled_ids: Optional[Iterable[str]] = None,
        severities: Optional[dict[str, Severity]] = None,
    ) -> None:
        self.registry = registry or default_registry
        self.rules: list[Rule] = self.registry.create_all(
            enabled_ids=enabled_ids,
            disabled_ids=disabled_ids,
            severities=severities,
        )

    def run(self, tree, source: str, file_path: str = "<module>") -> list[Diagnostic]:
        context = RuleContext(tree=tree, source=source, file_path=file_path)
        diagnostics: list[Diagnostic] = []

        for rule in self.rules:
            if not rule.enabled:
                continue
            for diagnostic in rule.check(context):
                diagnostics.append(self._with_path(diagnostic, file_path))

        diagnostics.sort(key=lambda d: d.sort_key())
        return diagnostics

    @staticmethod
    def _with_path(diagnostic: Diagnostic, file_path: str) -> Diagnostic:
        if diagnostic.file_path == file_path:
            return diagnostic
        return Diagnostic(
            rule_id=diagnostic.rule_id,
            message=diagnostic.message,
            line=diagnostic.line,
            column=diagnostic.column,
            severity=diagnostic.severity,
            file_path=file_path,
            end_line=diagnostic.end_line,
            end_column=diagnostic.end_column,
            fixable=diagnostic.fixable,
        )