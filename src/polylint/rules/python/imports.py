"""Import-related rules.

``UnusedImportRule`` reuses the semantic analyzer (see
:mod:`polylint.rules.python.unused` for the shared caching helper).
The other three are plain AST-pattern rules over the module body.
"""

from __future__ import annotations

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity
from polylint.languages.python import ast_nodes as ast
from polylint.rules.base import Rule, RuleContext, walk
from polylint.rules.python.unused import _semantic_diagnostics, _translate
from polylint.rules.registry import register


@register
class UnusedImportRule(Rule):
    id = "PLI001"
    name = "unused-import"
    description = "Imported name is never used."
    category = "imports"
    default_severity = Severity.WARNING

    _CODES = {"PL-UNUSED-IMPORT"}

    def check(self, context: RuleContext) -> list[Diagnostic]:
        return _translate(self, _semantic_diagnostics(context), self._CODES)


@register
class ImportNotAtTopRule(Rule):
    id = "PLI002"
    name = "import-not-at-top"
    description = "Import statements should appear at the top of the module."
    category = "imports"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        seen_non_import = False

        for stmt in context.tree.body:
            if isinstance(stmt, (ast.ImportStatement, ast.ImportFromStatement)):
                if seen_non_import:
                    diagnostics.append(
                        self.diagnostic_for(
                            "import statement is not at the top of the file", stmt,
                        )
                    )
                continue

            if isinstance(stmt, ast.ExpressionStatement) and isinstance(stmt.expression, ast.Literal) \
                    and isinstance(stmt.expression.value, str):
                continue  # a module docstring doesn't count as "real" code

            seen_non_import = True

        return diagnostics


@register
class DuplicateImportRule(Rule):
    id = "PLI003"
    name = "duplicate-import"
    description = "The same module (or name) is imported more than once."
    category = "imports"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        seen: set[tuple] = set()

        for node in walk(context.tree):
            if isinstance(node, ast.ImportStatement):
                key = ("import", node.module, node.alias)
                if key in seen:
                    diagnostics.append(
                        self.diagnostic_for(
                            f"'{node.module}' is imported more than once", node,
                        )
                    )
                seen.add(key)

            elif isinstance(node, ast.ImportFromStatement):
                for name, alias in node.names:
                    key = ("from", node.module, node.level, name, alias)
                    if key in seen:
                        diagnostics.append(
                            self.diagnostic_for(
                                f"'{name}' from '{node.module}' is imported more than once", node,
                            )
                        )
                    seen.add(key)

        return diagnostics


@register
class StarImportRule(Rule):
    id = "PLI004"
    name = "star-import"
    description = "Wildcard imports make it impossible to tell where a name came from."
    category = "imports"
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> list[Diagnostic]:
        diagnostics = []
        for node in walk(context.tree):
            if isinstance(node, ast.ImportFromStatement):
                for name, _alias in node.names:
                    if name == "*":
                        diagnostics.append(
                            self.diagnostic_for(
                                f"'from {node.module} import *' used", node,
                            )
                        )
        return diagnostics