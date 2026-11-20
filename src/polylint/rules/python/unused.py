"""Rules built on top of the semantic analyzer: undefined names, unused
variables and parameters, and unreachable code.

These rules don't walk the AST themselves -- they ask the
:class:`~polylint.languages.python.semantic.SemanticAnalyzer` to do it
once (cached on the :class:`~polylint.rules.base.RuleContext`, so
several rules sharing the same analysis only pay for it once) and then
translate the handful of semantic diagnostic codes they each care
about into this rule's own id and configured severity.
"""

from __future__ import annotations

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity
from polylint.languages.python.semantic import SemanticAnalyzer
from polylint.languages.python.semantic import Diagnostic as SemanticDiagnostic
from polylint.rules.base import Rule, RuleContext
from polylint.rules.registry import register

_SEMANTIC_CACHE_KEY = "python.semantic_diagnostics"


def _semantic_diagnostics(context: RuleContext) -> list[SemanticDiagnostic]:
    return context.cached(
        _SEMANTIC_CACHE_KEY,
        lambda: SemanticAnalyzer().analyze(context.tree),
    )


def _translate(rule: Rule, semantic_diagnostics: list[SemanticDiagnostic], codes: set[str]) -> list[Diagnostic]:
    return [
        rule.diagnostic(diag.message, diag.line, diag.column)
        for diag in semantic_diagnostics
        if diag.code in codes
    ]


@register
class UndefinedNameRule(Rule):
    id = "PLU001"
    name = "undefined-name"
    description = "Name is used but never defined, or used before it is assigned."
    category = "unused"
    default_severity = Severity.ERROR

    _CODES = {"PL-UNDEF", "PL-UNDEF-LOCAL"}

    def check(self, context: RuleContext) -> list[Diagnostic]:
        return _translate(self, _semantic_diagnostics(context), self._CODES)


@register
class UnusedVariableRule(Rule):
    id = "PLU002"
    name = "unused-variable"
    description = "Local variable is assigned but never used."
    category = "unused"
    default_severity = Severity.WARNING

    _CODES = {"PL-UNUSED-VAR"}

    def check(self, context: RuleContext) -> list[Diagnostic]:
        return _translate(self, _semantic_diagnostics(context), self._CODES)


@register
class UnusedParameterRule(Rule):
    id = "PLU003"
    name = "unused-parameter"
    description = "Function parameter is never used in the function body."
    category = "unused"
    default_severity = Severity.WARNING

    _CODES = {"PL-UNUSED-PARAM"}

    def check(self, context: RuleContext) -> list[Diagnostic]:
        return _translate(self, _semantic_diagnostics(context), self._CODES)


@register
class UnreachableCodeRule(Rule):
    id = "PLU004"
    name = "unreachable-code"
    description = "Code appears after an unconditional return/raise/break/continue."
    category = "unused"
    default_severity = Severity.WARNING

    _CODES = {"PL-UNREACHABLE"}

    def check(self, context: RuleContext) -> list[Diagnostic]:
        return _translate(self, _semantic_diagnostics(context), self._CODES)