"""Style rules for Python: things that are legal but usually smell."""

from __future__ import annotations

import dataclasses
from typing import Iterator

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity
from polylint.languages.python import ast_nodes as ast
from polylint.rules.base import Rule, RuleContext, walk
from polylint.rules.registry import register

_STATEMENT_LIST_FIELDS = {"body", "else_body", "finally_body"}


def _iter_statement_lists(node) -> Iterator[list]:
    """Yield every statement list (a function/class/if/while/for/try/
    except/with body) reachable from ``node``, at any depth -- but
    *only* fields actually named like a statement body, so ordinary
    lists of expressions (e.g. a list literal's elements) are never
    mistaken for a block of statements."""
    if node is None:
        return
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        for f in dataclasses.fields(node):
            value = getattr(node, f.name)
            if f.name in _STATEMENT_LIST_FIELDS and isinstance(value, list):
                yield value
            yield from _iter_statement_lists(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _iter_statement_lists(item)


def _is_docstring(stmt) -> bool:
    return (
        isinstance(stmt, ast.ExpressionStatement)
        and isinstance(stmt.expression, ast.Literal)
        and isinstance(stmt.expression.value, str)
    )


@register
class TooManyArgumentsRule(Rule):
    id = "PLS001"
    name = "too-many-arguments"
    description = "Function has more than the configured maximum number of parameters."
    category = "style"
    default_severity = Severity.WARNING
    max_arguments = 5

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for node in walk(context.tree):
            if not isinstance(node, ast.FunctionDefinition):
                continue
            count = sum(1 for p in node.parameters if p.name != "/")
            if count > self.max_arguments:
                diagnostics.append(
                    self.diagnostic_for(
                        f"function '{node.name}' has {count} parameters "
                        f"(more than {self.max_arguments})",
                        node,
                    )
                )
        return diagnostics


@register
class MissingDocstringRule(Rule):
    id = "PLS002"
    name = "missing-docstring"
    description = "Function or class has no docstring."
    category = "style"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for node in walk(context.tree):
            if isinstance(node, (ast.FunctionDefinition, ast.ClassDefinition)):
                if not node.body or not _is_docstring(node.body[0]):
                    kind = "function" if isinstance(node, ast.FunctionDefinition) else "class"
                    diagnostics.append(
                        self.diagnostic_for(
                            f"{kind} '{node.name}' has no docstring", node,
                        )
                    )
        return diagnostics


@register
class ComparisonToSingletonRule(Rule):
    id = "PLS003"
    name = "singleton-comparison"
    description = "Use 'is'/'is not' to compare against None/True/False, not '=='/'!='."
    category = "style"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for node in walk(context.tree):
            if not isinstance(node, ast.Comparison):
                continue
            operands = [node.left] + list(node.comparators)
            for operator, right in zip(node.operators, operands[1:]):
                if operator not in ("==", "!="):
                    continue
                if isinstance(right, ast.Literal) and (right.value is None or isinstance(right.value, bool)):
                    diagnostics.append(
                        self.diagnostic_for(
                            f"use 'is'/'is not' to compare against {right.value!r}, not '{operator}'",
                            node,
                        )
                    )
        return diagnostics


@register
class MultipleStatementsOnOneLineRule(Rule):
    id = "PLS004"
    name = "multiple-statements-per-line"
    description = "More than one statement written on the same line (e.g. via ';')."
    category = "style"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for statements in _iter_statement_lists(context.tree):
            seen_lines: dict[int, ast.ASTNode] = {}
            flagged_lines: set[int] = set()
            for stmt in statements:
                line = stmt.line
                if line in seen_lines and line not in flagged_lines:
                    diagnostics.append(
                        self.diagnostic_for(
                            "multiple statements on one line", seen_lines[line],
                        )
                    )
                    flagged_lines.add(line)
                else:
                    seen_lines.setdefault(line, stmt)
        return diagnostics