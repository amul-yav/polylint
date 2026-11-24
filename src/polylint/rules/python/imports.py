"""Import-related rules.

``UnusedImportRule`` reuses the semantic analyzer (see
:mod:`polylint.rules.python.unused` for the shared caching helper).
The other three are plain AST-pattern rules over the module body.
"""

from __future__ import annotations

import re

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity
from polylint.fix.fixer import Fix, TextEdit
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
        diagnostics = _translate(self, _semantic_diagnostics(context), self._CODES)
        imports = [
            node for node in walk(context.tree)
            if isinstance(node, (ast.ImportStatement, ast.ImportFromStatement))
        ]
        result = []
        for diagnostic in diagnostics:
            fix = self._fix_for_diagnostic(context, diagnostic, imports)
            if fix is not None:
                context.add_fix(fix)
                diagnostic = Diagnostic(
                    rule_id=diagnostic.rule_id,
                    message=diagnostic.message,
                    line=diagnostic.line,
                    column=diagnostic.column,
                    severity=diagnostic.severity,
                    file_path=diagnostic.file_path,
                    end_line=diagnostic.end_line,
                    end_column=diagnostic.end_column,
                    fixable=True,
                )
            result.append(diagnostic)
        return result

    def _fix_for_diagnostic(self, context, diagnostic, imports):
        """Delete a verified, single-name import while preserving comments."""
        line_number = diagnostic.line
        if line_number < 1 or line_number > len(context.source.splitlines()):
            return None
        lines = context.source.splitlines(keepends=True)
        line = lines[line_number - 1]
        if "\n" in line.rstrip("\r\n") or "\\" in line:
            return None

        candidates = [node for node in imports if node.line == line_number]
        if len(candidates) != 1:
            return None
        node = candidates[0]
        prefix = re.match(r"^[ \t]*", line).group(0)
        body = line[len(prefix):].rstrip("\r\n")
        comment_at = body.find("#")
        code = body[:comment_at].rstrip() if comment_at >= 0 else body.rstrip()

        if isinstance(node, ast.ImportStatement):
            if not re.fullmatch(r"import\s+[^,;\s]+(?:\s+as\s+[A-Za-z_]\w*)?", code):
                return None
            expected = f"import {node.module}"
            if node.alias:
                expected += f" as {node.alias}"
        else:
            if len(node.names) != 1:
                return None
            name, alias = node.names[0]
            if not re.fullmatch(r"from\s+[^;]+\s+import\s+[^,()\s]+(?:\s+as\s+[A-Za-z_]\w*)?", code):
                return None
            module = "." * node.level + node.module
            expected = f"from {module} import {name}"
            if alias:
                expected += f" as {alias}"

        if code != expected:
            return None

        line_start = sum(len(item) for item in lines[:line_number - 1])
        code_start = line_start + len(prefix)
        code_end = code_start + len(code)
        if comment_at >= 0:
            # Keep the comment text and indentation, dropping only code and
            # the whitespace separating it from the comment.
            end = line_start + len(prefix) + comment_at
            replacement = ""
        else:
            # Remove the whole standalone statement, including its newline.
            end = line_start + len(line)
            code_start = line_start
            replacement = ""
        return Fix(self.id, diagnostic.message, (TextEdit(code_start, end, replacement),))


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
