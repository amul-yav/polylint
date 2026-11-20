"""Naming-convention rules for Python.

These are plain AST-pattern rules: they don't need the semantic
analyzer, just :func:`polylint.rules.base.walk` over the tree.
"""

from __future__ import annotations

import re
from typing import Iterator

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity
from polylint.languages.python import ast_nodes as ast
from polylint.rules.base import Rule, RuleContext, walk
from polylint.rules.registry import register

SNAKE_CASE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
PASCAL_CASE_RE = re.compile(r"^_?[A-Z][a-zA-Z0-9]*$")
AMBIGUOUS_NAMES = {"l", "O", "I"}


def is_snake_case(name: str) -> bool:
    return bool(SNAKE_CASE_RE.match(name))


def is_pascal_case(name: str) -> bool:
    return bool(PASCAL_CASE_RE.match(name))


def _flatten_identifiers(target: ast.ASTNode | None) -> Iterator[ast.Identifier]:
    """Yield every plain name bound by an assignment target, including
    through tuple/list unpacking and starred targets. Attribute and
    subscript targets (``obj.attr = ...``) introduce no new name."""
    if target is None:
        return
    if isinstance(target, ast.Identifier):
        yield target
    elif isinstance(target, (ast.TupleExpression, ast.ListExpression)):
        for element in target.elements:
            yield from _flatten_identifiers(element)
    elif isinstance(target, ast.StarredExpression):
        yield from _flatten_identifiers(target.value)


@register
class FunctionNamingRule(Rule):
    id = "PLN001"
    name = "function-naming"
    description = "Function and method names should be snake_case."
    category = "naming"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for node in walk(context.tree):
            if isinstance(node, ast.FunctionDefinition) and not is_snake_case(node.name):
                diagnostics.append(
                    self.diagnostic_for(
                        f"function name '{node.name}' should be snake_case", node,
                    )
                )
        return diagnostics


@register
class ClassNamingRule(Rule):
    id = "PLN002"
    name = "class-naming"
    description = "Class names should be PascalCase."
    category = "naming"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for node in walk(context.tree):
            if isinstance(node, ast.ClassDefinition) and not is_pascal_case(node.name):
                diagnostics.append(
                    self.diagnostic_for(
                        f"class name '{node.name}' should be PascalCase", node,
                    )
                )
        return diagnostics


@register
class VariableNamingRule(Rule):
    id = "PLN003"
    name = "variable-naming"
    description = "Variable names should be snake_case (ALL_CAPS constants are exempt)."
    category = "naming"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for node in walk(context.tree):
            if not isinstance(node, ast.Assignment):
                continue
            for target in node.targets:
                for identifier in _flatten_identifiers(target):
                    name = identifier.name
                    if name.isupper():
                        continue  # ALL_CAPS constants are intentionally exempt
                    if not is_snake_case(name):
                        diagnostics.append(
                            self.diagnostic_for(
                                f"variable name '{name}' should be snake_case", identifier,
                            )
                        )
        return diagnostics


@register
class AmbiguousNameRule(Rule):
    id = "PLN004"
    name = "ambiguous-name"
    description = "Avoid 'l', 'O' and 'I' as names: they are easily confused with 1 and 0."
    category = "naming"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for node in walk(context.tree):
            if isinstance(node, ast.Parameter) and node.name in AMBIGUOUS_NAMES:
                diagnostics.append(
                    self.diagnostic_for(
                        f"ambiguous parameter name '{node.name}'", node,
                    )
                )
            elif isinstance(node, ast.Assignment):
                for target in node.targets:
                    for identifier in _flatten_identifiers(target):
                        if identifier.name in AMBIGUOUS_NAMES:
                            diagnostics.append(
                                self.diagnostic_for(
                                    f"ambiguous variable name '{identifier.name}'", identifier,
                                )
                            )
        return diagnostics