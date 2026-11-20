"""Semantic analyzer for PolyLint's Python front end.

Takes the AST produced by :class:`polylint.languages.python.parser.Parser`
and performs two passes over it:

1. **Declaration pass** -- walks every statement and expression, builds the
   scope tree (module / function / class / lambda / comprehension scopes)
   and populates each scope's symbol table with every name it binds
   (assignments, parameters, function/class names, imports, for-targets,
   with-targets, except-names, global/nonlocal declarations).

2. **Check pass** -- walks the tree again in program order, resolving every
   *use* of a name against the scope tree (Python's LEGB rule) and
   reporting diagnostics: undefined names, names used before assignment,
   unused variables/imports, redefinition/shadowing, misplaced control
   flow, unreachable code, and a handful of type/correctness smells
   (mutable default arguments, `is` against a literal, duplicate dict
   keys, self-comparison, always-true assert tuples).

This module intentionally does not implement full Python semantics
(e.g. it does not model conditional/narrowed control flow, star-import
namespaces, or real type inference) -- it favours simple, predictable
rules that are easy to reason about and extend, in the same spirit as
the lexer and parser.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from polylint.languages.python import ast_nodes as ast
from polylint.languages.python.scope import Scope, ScopeKind
from polylint.languages.python.symbols import Symbol, SymbolKind


BUILTIN_NAMES = {
    "print", "len", "range", "int", "float", "str", "bool", "list", "dict",
    "set", "tuple", "object", "type", "isinstance", "issubclass", "super",
    "open", "input", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "sum", "min", "max", "abs", "round", "all", "any", "repr", "format",
    "getattr", "setattr", "hasattr", "delattr", "iter", "next", "id",
    "hash", "callable", "vars", "dir", "globals", "locals", "exec", "eval",
    "__name__", "__file__", "__doc__", "__import__", "staticmethod",
    "classmethod", "property", "frozenset", "bytes", "bytearray",
    "complex", "slice", "NotImplemented", "Ellipsis", "__debug__",
    "Exception", "BaseException", "ValueError", "TypeError", "KeyError",
    "IndexError", "AttributeError", "NameError", "StopIteration",
    "RuntimeError", "ZeroDivisionError", "ImportError", "OSError",
    "FileNotFoundError", "NotImplementedError", "ArithmeticError",
    "True", "False", "None",
}

MAGIC_METHODS_RETURNING_NONE = {"__init__"}


class Severity(Enum):
    ERROR = auto()
    WARNING = auto()


@dataclass
class Diagnostic:
    code: str
    message: str
    line: int
    column: int
    severity: Severity

    @property
    def is_error(self) -> bool:
        return self.severity is Severity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity is Severity.WARNING

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        level = "error" if self.is_error else "warning"
        return f"[{self.code}] {level}: {self.message} ({self.line}:{self.column})"


class SemanticAnalyzer:
    """Builds scopes/symbols for a Python :class:`ast.Module` and reports
    diagnostics about undefined names, unused bindings, scoping mistakes,
    bad control flow, and a few correctness smells."""

    def __init__(self) -> None:
        self.diagnostics: list[Diagnostic] = []
        self.module_scope: Optional[Scope] = None
        # id(node) -> Scope created for that node during the declare pass.
        self._scope_of: dict[int, Scope] = {}

    # ------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------

    def analyze(self, tree: ast.Module) -> list[Diagnostic]:
        self.diagnostics = []
        self._scope_of = {}
        self.module_scope = Scope(ScopeKind.MODULE, parent=None, name="<module>")

        self._declare_block(tree.body, self.module_scope)
        self._check_block(tree.body, self.module_scope, set())
        self._report_unused(self.module_scope, is_module=True)

        return self.diagnostics

    # ------------------------------------------------------------
    # Diagnostic helpers
    # ------------------------------------------------------------

    def _error(self, code: str, message: str, node: ast.ASTNode) -> None:
        self.diagnostics.append(
            Diagnostic(code, message, node.line, node.column, Severity.ERROR)
        )

    def _warn(self, code: str, message: str, node: ast.ASTNode) -> None:
        self.diagnostics.append(
            Diagnostic(code, message, node.line, node.column, Severity.WARNING)
        )

    def has_errors(self) -> bool:
        return any(d.is_error for d in self.diagnostics)

    # ==============================================================
    # Pass 1: declaration
    # ==============================================================

    def _declare_block(self, body: list[ast.ASTNode], scope: Scope) -> None:
        for stmt in body:
            self._declare_stmt(stmt, scope)

    def _declare_stmt(self, stmt: ast.ASTNode, scope: Scope) -> None:
        if isinstance(stmt, ast.Assignment):
            for target in stmt.targets:
                self._declare_target(target, scope, SymbolKind.VARIABLE)
            self._declare_in_expr(stmt.value, scope)

        elif isinstance(stmt, ast.AugmentedAssignment):
            self._declare_target(stmt.target, scope, SymbolKind.VARIABLE)
            self._declare_in_expr(stmt.value, scope)

        elif isinstance(stmt, ast.ExpressionStatement):
            self._declare_in_expr(stmt.expression, scope)

        elif isinstance(stmt, ast.ReturnStatement):
            self._declare_in_expr(stmt.value, scope)

        elif isinstance(stmt, ast.RaiseStatement):
            self._declare_in_expr(stmt.exception, scope)
            self._declare_in_expr(stmt.cause, scope)

        elif isinstance(stmt, ast.AssertStatement):
            self._declare_in_expr(stmt.test, scope)
            self._declare_in_expr(stmt.message, scope)

        elif isinstance(stmt, ast.DeleteStatement):
            for target in stmt.targets:
                self._declare_in_expr(target, scope)

        elif isinstance(stmt, ast.GlobalStatement):
            for name in stmt.names:
                scope.declare_global(name)

        elif isinstance(stmt, ast.NonlocalStatement):
            for name in stmt.names:
                scope.declare_nonlocal(name)

        elif isinstance(stmt, ast.ImportStatement):
            bound_name = stmt.alias or stmt.module.split(".")[0]
            scope.declare(bound_name, SymbolKind.IMPORT, stmt.line, stmt.column, stmt)

        elif isinstance(stmt, ast.ImportFromStatement):
            for name, alias in stmt.names:
                if name == "*":
                    continue
                bound_name = alias or name
                scope.declare(bound_name, SymbolKind.IMPORT, stmt.line, stmt.column, stmt)

        elif isinstance(stmt, ast.IfStatement):
            self._declare_in_expr(stmt.test, scope)
            self._declare_block(stmt.body, scope)
            for condition, branch_body in stmt.elif_branches:
                self._declare_in_expr(condition, scope)
                self._declare_block(branch_body, scope)
            self._declare_block(stmt.else_body, scope)

        elif isinstance(stmt, ast.WhileStatement):
            self._declare_in_expr(stmt.test, scope)
            self._declare_block(stmt.body, scope)
            self._declare_block(stmt.else_body, scope)

        elif isinstance(stmt, ast.ForStatement):
            self._declare_in_expr(stmt.iterable, scope)
            self._declare_target(stmt.target, scope, SymbolKind.VARIABLE)
            self._declare_block(stmt.body, scope)
            self._declare_block(stmt.else_body, scope)

        elif isinstance(stmt, ast.TryStatement):
            self._declare_block(stmt.body, scope)
            for handler in stmt.handlers:
                self._declare_in_expr(handler.exception, scope)
                if handler.name:
                    scope.declare(
                        handler.name, SymbolKind.EXCEPTION,
                        handler.line, handler.column, handler,
                    )
                self._declare_block(handler.body, scope)
            self._declare_block(stmt.else_body, scope)
            self._declare_block(stmt.finally_body, scope)

        elif isinstance(stmt, ast.WithStatement):
            for context, target in stmt.items:
                self._declare_in_expr(context, scope)
                if target is not None:
                    self._declare_target(target, scope, SymbolKind.VARIABLE)
            self._declare_block(stmt.body, scope)

        elif isinstance(stmt, ast.FunctionDefinition):
            for decorator in stmt.decorators:
                self._declare_in_expr(decorator, scope)
            self._declare_in_expr(stmt.returns, scope)
            for param in stmt.parameters:
                self._declare_in_expr(param.default, scope)
                self._declare_in_expr(param.annotation, scope)

            scope.declare(stmt.name, SymbolKind.FUNCTION, stmt.line, stmt.column, stmt)

            function_scope = Scope(ScopeKind.FUNCTION, parent=scope, name=stmt.name)
            self._scope_of[id(stmt)] = function_scope

            for param in stmt.parameters:
                if param.name == "/":
                    continue
                function_scope.declare(
                    param.name, SymbolKind.PARAMETER, param.line, param.column, param,
                )

            self._declare_block(stmt.body, function_scope)

        elif isinstance(stmt, ast.ClassDefinition):
            for decorator in stmt.decorators:
                self._declare_in_expr(decorator, scope)
            for base in stmt.bases:
                self._declare_in_expr(base, scope)

            scope.declare(stmt.name, SymbolKind.CLASS, stmt.line, stmt.column, stmt)

            class_scope = Scope(ScopeKind.CLASS, parent=scope, name=stmt.name)
            self._scope_of[id(stmt)] = class_scope

            self._declare_block(stmt.body, class_scope)

        # PassStatement / BreakStatement / ContinueStatement: nothing to declare.

    def _declare_target(self, target: Optional[ast.ASTNode], scope: Scope, kind: SymbolKind) -> None:
        """Declare every Identifier appearing in an assignment-style target
        (handles plain names, tuple/list unpacking and starred targets).
        Attribute/subscript targets (``obj.attr = ...`` / ``obj[0] = ...``)
        do not introduce a new name -- the object itself must already
        exist, which the check pass verifies."""
        if target is None:
            return

        if isinstance(target, ast.Identifier):
            scope.declare(target.name, kind, target.line, target.column, target)
        elif isinstance(target, (ast.TupleExpression, ast.ListExpression)):
            for element in target.elements:
                self._declare_target(element, scope, kind)
        elif isinstance(target, ast.StarredExpression):
            self._declare_target(target.value, scope, kind)
        elif isinstance(target, (ast.AttributeAccess, ast.SubscriptExpression)):
            # Not a new binding; the base object is checked as a use.
            self._declare_in_expr(target, scope)
        else:
            self._declare_in_expr(target, scope)

    def _declare_in_expr(self, node: Optional[ast.ASTNode], scope: Scope) -> None:
        """Walk an expression subtree purely to discover nested scopes
        (lambdas and list comprehensions) and build their scope objects."""
        if node is None:
            return

        if isinstance(node, ast.LambdaExpression):
            lambda_scope = Scope(ScopeKind.LAMBDA, parent=scope, name="<lambda>")
            self._scope_of[id(node)] = lambda_scope
            for param in node.parameters:
                self._declare_in_expr(param.default, scope)
                lambda_scope.declare(
                    param.name, SymbolKind.PARAMETER, param.line, param.column, param,
                )
            self._declare_in_expr(node.body, lambda_scope)
            return

        if isinstance(node, ast.ListComprehension):
            comp_scope = Scope(ScopeKind.COMPREHENSION, parent=scope, name="<listcomp>")
            self._scope_of[id(node)] = comp_scope
            for index, generator in enumerate(node.generators):
                # Only the first generator's iterable is evaluated in the
                # enclosing scope; the rest (and the targets) live in the
                # comprehension's own scope, matching Python 3 semantics.
                target_scope = scope if index == 0 else comp_scope
                self._declare_in_expr(generator.iterable, target_scope)
                self._declare_target(generator.target, comp_scope, SymbolKind.VARIABLE)
                for condition in generator.conditions:
                    self._declare_in_expr(condition, comp_scope)
            self._declare_in_expr(node.element, comp_scope)
            return

        self._generic_declare(node, scope)

    def _generic_declare(self, node: ast.ASTNode, scope: Scope) -> None:
        for f in dataclasses.fields(node):
            self._declare_value(getattr(node, f.name), scope)

    def _declare_value(self, value, scope: Scope) -> None:
        if isinstance(value, ast.ASTNode):
            self._declare_in_expr(value, scope)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self._declare_value(item, scope)

    # ==============================================================
    # Pass 2: checking (undefined / unused / scoping / control flow)
    # ==============================================================

    def _check_block(self, body: list[ast.ASTNode], scope: Scope, defined: set) -> None:
        terminated = False
        for stmt in body:
            if terminated:
                self._warn(
                    "PL-UNREACHABLE", "unreachable code", stmt,
                )
                terminated = False  # only warn once per dead run
            self._check_stmt(stmt, scope, defined)
            if isinstance(
                stmt,
                (ast.ReturnStatement, ast.RaiseStatement, ast.BreakStatement, ast.ContinueStatement),
            ):
                terminated = True

    def _bind(self, name: str, scope: Scope, defined: set) -> None:
        defined.add(name)

    def _bind_target(self, target: Optional[ast.ASTNode], scope: Scope, defined: set) -> None:
        if target is None:
            return
        if isinstance(target, ast.Identifier):
            self._bind(target.name, scope, defined)
        elif isinstance(target, (ast.TupleExpression, ast.ListExpression)):
            for element in target.elements:
                self._bind_target(element, scope, defined)
        elif isinstance(target, ast.StarredExpression):
            self._bind_target(target.value, scope, defined)
        elif isinstance(target, (ast.AttributeAccess, ast.SubscriptExpression)):
            # obj.attr = x / obj[0] = x: obj must already exist.
            self._check_expr(target, scope, defined)
        else:
            self._check_expr(target, scope, defined)

    def _check_stmt(self, stmt: ast.ASTNode, scope: Scope, defined: set) -> None:
        if isinstance(stmt, ast.Assignment):
            self._check_expr(stmt.value, scope, defined)
            for target in stmt.targets:
                self._bind_target(target, scope, defined)

        elif isinstance(stmt, ast.AugmentedAssignment):
            # The target is read *and* written: it must already exist.
            self._check_expr(stmt.target, scope, defined)
            self._check_expr(stmt.value, scope, defined)
            self._bind_target(stmt.target, scope, defined)

        elif isinstance(stmt, ast.ExpressionStatement):
            self._check_expr(stmt.expression, scope, defined)

        elif isinstance(stmt, ast.ReturnStatement):
            if scope.kind not in (ScopeKind.FUNCTION, ScopeKind.LAMBDA):
                self._error("PL-RETURN-OUTSIDE-FUNCTION", "'return' outside function", stmt)
            if stmt.value is not None:
                self._check_expr(stmt.value, scope, defined)
                if scope.kind == ScopeKind.FUNCTION and scope.name in MAGIC_METHODS_RETURNING_NONE:
                    if not (isinstance(stmt.value, ast.Literal) and stmt.value.value is None):
                        self._warn(
                            "PL-INIT-RETURNS-VALUE",
                            f"'{scope.name}' should not return a value",
                            stmt,
                        )

        elif isinstance(stmt, ast.BreakStatement):
            if not getattr(scope, "_polylint_in_loop", False):
                self._error("PL-BREAK-OUTSIDE-LOOP", "'break' outside loop", stmt)

        elif isinstance(stmt, ast.ContinueStatement):
            if not getattr(scope, "_polylint_in_loop", False):
                self._error("PL-CONTINUE-OUTSIDE-LOOP", "'continue' outside loop", stmt)

        elif isinstance(stmt, ast.PassStatement):
            pass

        elif isinstance(stmt, ast.RaiseStatement):
            self._check_expr(stmt.exception, scope, defined)
            self._check_expr(stmt.cause, scope, defined)

        elif isinstance(stmt, ast.AssertStatement):
            self._check_expr(stmt.test, scope, defined)
            self._check_expr(stmt.message, scope, defined)
            if isinstance(stmt.test, ast.TupleExpression) and len(stmt.test.elements) > 0:
                self._warn(
                    "PL-ASSERT-TUPLE",
                    "assertion is always true; did you mean a tuple of conditions?",
                    stmt,
                )

        elif isinstance(stmt, ast.DeleteStatement):
            for target in stmt.targets:
                self._check_expr(target, scope, defined)
                if isinstance(target, ast.Identifier):
                    defined.discard(target.name)

        elif isinstance(stmt, ast.GlobalStatement):
            pass

        elif isinstance(stmt, ast.NonlocalStatement):
            for name in stmt.names:
                if scope.nearest_enclosing_function() is None or scope.resolve(name) is None:
                    self._error(
                        "PL-NONLOCAL-NO-BINDING",
                        f"no binding for nonlocal '{name}' found",
                        stmt,
                    )

        elif isinstance(stmt, ast.ImportStatement):
            bound_name = stmt.alias or stmt.module.split(".")[0]
            self._bind(bound_name, scope, defined)

        elif isinstance(stmt, ast.ImportFromStatement):
            for name, alias in stmt.names:
                if name == "*":
                    self._warn(
                        "PL-STAR-IMPORT",
                        f"'from {stmt.module} import *' makes names unresolvable",
                        stmt,
                    )
                    continue
                self._bind(alias or name, scope, defined)

        elif isinstance(stmt, ast.IfStatement):
            self._check_expr(stmt.test, scope, defined)
            self._check_block(stmt.body, scope, defined)
            for condition, branch_body in stmt.elif_branches:
                self._check_expr(condition, scope, defined)
                self._check_block(branch_body, scope, defined)
            self._check_block(stmt.else_body, scope, defined)

        elif isinstance(stmt, ast.WhileStatement):
            self._check_expr(stmt.test, scope, defined)
            self._enter_loop(scope, stmt.body, defined)
            self._check_block(stmt.else_body, scope, defined)

        elif isinstance(stmt, ast.ForStatement):
            self._check_expr(stmt.iterable, scope, defined)
            self._bind_target(stmt.target, scope, defined)
            self._enter_loop(scope, stmt.body, defined)
            self._check_block(stmt.else_body, scope, defined)

        elif isinstance(stmt, ast.TryStatement):
            self._check_block(stmt.body, scope, defined)
            for handler in stmt.handlers:
                self._check_expr(handler.exception, scope, defined)
                if handler.name:
                    self._bind(handler.name, scope, defined)
                self._check_block(handler.body, scope, defined)
            self._check_block(stmt.else_body, scope, defined)
            self._check_block(stmt.finally_body, scope, defined)

        elif isinstance(stmt, ast.WithStatement):
            for context, target in stmt.items:
                self._check_expr(context, scope, defined)
                if target is not None:
                    self._bind_target(target, scope, defined)
            self._check_block(stmt.body, scope, defined)

        elif isinstance(stmt, ast.FunctionDefinition):
            self._check_function(stmt, scope, defined)

        elif isinstance(stmt, ast.ClassDefinition):
            self._check_class(stmt, scope, defined)

    def _enter_loop(self, scope: Scope, body: list[ast.ASTNode], defined: set) -> None:
        previously = getattr(scope, "_polylint_in_loop", False)
        scope._polylint_in_loop = True
        try:
            self._check_block(body, scope, defined)
        finally:
            scope._polylint_in_loop = previously

    # ---------------------------------------------------------
    # Functions / classes
    # ---------------------------------------------------------

    def _check_function(self, stmt: ast.FunctionDefinition, scope: Scope, defined: set) -> None:
        for decorator in stmt.decorators:
            self._check_expr(decorator, scope, defined)
        for param in stmt.parameters:
            if param.annotation is not None:
                self._check_expr(param.annotation, scope, defined)
            if param.default is not None:
                self._check_expr(param.default, scope, defined)
                if isinstance(param.default, (ast.ListExpression, ast.DictionaryExpression, ast.SetExpression)):
                    self._warn(
                        "PL-MUTABLE-DEFAULT",
                        f"mutable default argument for parameter '{param.name}'",
                        param,
                    )
        if stmt.returns is not None:
            self._check_expr(stmt.returns, scope, defined)

        names_seen: set[str] = set()
        for param in stmt.parameters:
            if param.name == "/":
                continue
            if param.name in names_seen:
                self._error(
                    "PL-DUP-PARAM", f"duplicate parameter '{param.name}'", param,
                )
            names_seen.add(param.name)

        self._bind(stmt.name, scope, defined)

        function_scope = self._scope_of[id(stmt)]
        function_defined = {p.name for p in stmt.parameters if p.name != "/"}
        self._check_block(stmt.body, function_scope, function_defined)
        self._report_unused(function_scope)

    def _check_class(self, stmt: ast.ClassDefinition, scope: Scope, defined: set) -> None:
        for decorator in stmt.decorators:
            self._check_expr(decorator, scope, defined)
        for base in stmt.bases:
            self._check_expr(base, scope, defined)

        self._bind(stmt.name, scope, defined)

        class_scope = self._scope_of[id(stmt)]
        self._check_block(stmt.body, class_scope, set())
        self._check_self_attributes(stmt, class_scope)
        self._report_unused(class_scope, is_class=True)

    def _check_self_attributes(self, stmt: ast.ClassDefinition, class_scope: Scope) -> None:
        """Very small "type-ish" check: warn when a method reads
        ``self.<attr>`` for an attribute that is never assigned anywhere
        in the class (and isn't a method/class attribute either)."""
        assigned_attrs: set[str] = set()
        method_names = {
            member.name for member in stmt.body if isinstance(member, ast.FunctionDefinition)
        }

        def collect_assigned(node: Optional[ast.ASTNode]) -> None:
            if node is None:
                return
            if isinstance(node, ast.Assignment):
                for target in node.targets:
                    if isinstance(target, ast.AttributeAccess) and isinstance(target.object, ast.Identifier) and target.object.name == "self":
                        assigned_attrs.add(target.attribute)
                collect_assigned(node.value)
            elif isinstance(node, ast.AugmentedAssignment):
                if isinstance(node.target, ast.AttributeAccess) and isinstance(node.target.object, ast.Identifier) and node.target.object.name == "self":
                    assigned_attrs.add(node.target.attribute)
            for f in dataclasses.fields(node):
                value = getattr(node, f.name)
                if isinstance(value, ast.ASTNode):
                    collect_assigned(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, ast.ASTNode):
                            collect_assigned(item)

        for member in stmt.body:
            if isinstance(member, ast.FunctionDefinition):
                for inner in member.body:
                    collect_assigned(inner)

        def check_reads(node: Optional[ast.ASTNode]) -> None:
            if node is None:
                return
            if isinstance(node, ast.AttributeAccess) and isinstance(node.object, ast.Identifier) and node.object.name == "self":
                if (
                    node.attribute not in assigned_attrs
                    and node.attribute not in method_names
                    and not node.attribute.startswith("__")
                ):
                    self._warn(
                        "PL-UNDEFINED-ATTRIBUTE",
                        f"attribute 'self.{node.attribute}' is never assigned in this class",
                        node,
                    )
                return
            for f in dataclasses.fields(node):
                value = getattr(node, f.name)
                if isinstance(value, ast.ASTNode):
                    check_reads(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, ast.ASTNode):
                            check_reads(item)

        for member in stmt.body:
            if isinstance(member, ast.FunctionDefinition):
                for inner in member.body:
                    check_reads(inner)

    # ---------------------------------------------------------
    # Expressions
    # ---------------------------------------------------------

    def _check_expr(self, node: Optional[ast.ASTNode], scope: Scope, defined: set) -> None:
        if node is None:
            return

        if isinstance(node, ast.Identifier):
            self._check_name_use(node, scope, defined)
            return

        if isinstance(node, ast.LambdaExpression):
            self._check_lambda(node, scope, defined)
            return

        if isinstance(node, ast.ListComprehension):
            self._check_listcomp(node, scope, defined)
            return

        if isinstance(node, ast.Comparison):
            self._check_comparison(node, scope, defined)
            return

        if isinstance(node, ast.DictionaryExpression):
            self._check_dictionary(node, scope, defined)
            return

        if isinstance(node, ast.NamedExpression):
            # Walrus: value computed first, then target is bound in the
            # *current* scope (not the comprehension's, but we keep this
            # simple and bind into whichever scope we're checking).
            self._check_expr(node.value, scope, defined)
            self._bind_target(node.target, scope, defined)
            return

        self._generic_check(node, scope, defined)

    def _generic_check(self, node: ast.ASTNode, scope: Scope, defined: set) -> None:
        for f in dataclasses.fields(node):
            self._check_value(getattr(node, f.name), scope, defined)

    def _check_value(self, value, scope: Scope, defined: set) -> None:
        if isinstance(value, ast.ASTNode):
            self._check_expr(value, scope, defined)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self._check_value(item, scope, defined)

    def _check_name_use(self, node: ast.Identifier, scope: Scope, defined: set) -> None:
        name = node.name

        if name in BUILTIN_NAMES:
            return

        if name in defined:
            symbol = scope.resolve_local(name)
            if symbol is not None:
                symbol.used = True
            return

        local_symbol = scope.resolve_local(name)
        if (
            local_symbol is not None
            and name not in scope.globals
            and name not in scope.nonlocals
        ):
            self._error(
                "PL-UNDEF-LOCAL",
                f"local variable '{name}' referenced before assignment",
                node,
            )
            return

        symbol = scope.resolve(name)
        if symbol is not None:
            symbol.used = True
            return

        self._error("PL-UNDEF", f"undefined name '{name}'", node)

    def _check_lambda(self, node: ast.LambdaExpression, scope: Scope, defined: set) -> None:
        for param in node.parameters:
            if param.default is not None:
                self._check_expr(param.default, scope, defined)

        lambda_scope = self._scope_of[id(node)]
        lambda_defined = {p.name for p in node.parameters}
        self._check_expr(node.body, lambda_scope, lambda_defined)
        self._report_unused(lambda_scope, silent_unused_params=True)

    def _check_listcomp(self, node: ast.ListComprehension, scope: Scope, defined: set) -> None:
        comp_scope = self._scope_of[id(node)]
        comp_defined: set = set()

        for index, generator in enumerate(node.generators):
            if index == 0:
                self._check_expr(generator.iterable, scope, defined)
            else:
                self._check_expr(generator.iterable, comp_scope, comp_defined)
            self._bind_target(generator.target, comp_scope, comp_defined)
            for condition in generator.conditions:
                self._check_expr(condition, comp_scope, comp_defined)

        self._check_expr(node.element, comp_scope, comp_defined)
        self._report_unused(comp_scope, silent_unused_params=True)

    def _check_comparison(self, node: ast.Comparison, scope: Scope, defined: set) -> None:
        self._check_expr(node.left, scope, defined)
        operands = [node.left] + list(node.comparators)
        for comparator in node.comparators:
            self._check_expr(comparator, scope, defined)

        for operator, left_operand, right_operand in zip(node.operators, operands, operands[1:]):
            right_is_bare_literal = (
                isinstance(right_operand, ast.Literal)
                and right_operand.value is not None
                and not isinstance(right_operand.value, bool)
            )
            if operator in ("is", "is not") and right_is_bare_literal:
                self._warn(
                    "PL-IS-LITERAL",
                    "use '==' to compare against a literal value, not 'is'",
                    node,
                )
            if (
                isinstance(left_operand, ast.Identifier)
                and isinstance(right_operand, ast.Identifier)
                and left_operand.name == right_operand.name
                and operator in ("==", "is")
            ):
                self._warn(
                    "PL-SELF-COMPARISON",
                    f"'{left_operand.name} {operator} {right_operand.name}' always evaluates the same way",
                    node,
                )

    def _check_dictionary(self, node: ast.DictionaryExpression, scope: Scope, defined: set) -> None:
        seen_keys: set = set()
        for key, value in node.entries:
            self._check_expr(key, scope, defined)
            self._check_expr(value, scope, defined)
            if isinstance(key, ast.Literal) and isinstance(key.value, (str, int, float, bool, type(None))):
                if key.value in seen_keys:
                    self._warn(
                        "PL-DUPLICATE-KEY",
                        f"duplicate dictionary key {key.value!r}",
                        node,
                    )
                seen_keys.add(key.value)

    # ---------------------------------------------------------
    # Unused-name reporting
    # ---------------------------------------------------------

    def _report_unused(
        self,
        scope: Scope,
        is_module: bool = False,
        is_class: bool = False,
        silent_unused_params: bool = False,
    ) -> None:
        for symbol in scope.symbols:
            if (
                symbol.name in BUILTIN_NAMES
                and symbol.kind in (SymbolKind.VARIABLE, SymbolKind.PARAMETER, SymbolKind.FUNCTION, SymbolKind.CLASS)
            ):
                self._warn(
                    "PL-SHADOW-BUILTIN",
                    f"'{symbol.name}' shadows a builtin name",
                    symbol.node,
                )

            if (
                not scope.is_module_scope()
                and symbol.kind in (SymbolKind.VARIABLE, SymbolKind.PARAMETER)
                and not symbol.name.startswith("_")
                and symbol.name not in scope.globals
                and symbol.name not in scope.nonlocals
            ):
                for enclosing in scope.enclosing_lookup_scopes():
                    if enclosing.symbols.contains(symbol.name):
                        self._warn(
                            "PL-SHADOW-OUTER",
                            f"'{symbol.name}' shadows a name from an enclosing scope",
                            symbol.node,
                        )
                        break

            if symbol.used:
                continue
            if symbol.name.startswith("_"):
                continue
            if symbol.name in scope.globals or symbol.name in scope.nonlocals:
                continue
            if symbol.kind == SymbolKind.IMPORT:
                self._warn(
                    "PL-UNUSED-IMPORT", f"imported name '{symbol.name}' is unused", symbol.node,
                )
            elif symbol.kind == SymbolKind.VARIABLE and not is_module and not is_class:
                self._warn(
                    "PL-UNUSED-VAR", f"local variable '{symbol.name}' is assigned but never used", symbol.node,
                )
            elif symbol.kind == SymbolKind.PARAMETER and not silent_unused_params:
                self._warn(
                    "PL-UNUSED-PARAM", f"parameter '{symbol.name}' is unused", symbol.node,
                )