
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ASTNode:
    line: int = 0
    column: int = 0


# -------------------------
# Module
# -------------------------

@dataclass
class Module(ASTNode):
    body: list[ASTNode] = field(default_factory=list)


# -------------------------
# Statements
# -------------------------

@dataclass
class ExpressionStatement(ASTNode):
    expression: ASTNode | None = None


@dataclass
class Assignment(ASTNode):
    targets: list[ASTNode] = field(default_factory=list)
    value: ASTNode | None = None


@dataclass
class AugmentedAssignment(ASTNode):
    target: ASTNode | None = None
    operator: str = ""
    value: ASTNode | None = None


@dataclass
class ReturnStatement(ASTNode):
    value: ASTNode | None = None


@dataclass
class BreakStatement(ASTNode):
    pass


@dataclass
class ContinueStatement(ASTNode):
    pass


@dataclass
class PassStatement(ASTNode):
    pass


@dataclass
class DeleteStatement(ASTNode):
    targets: list[ASTNode] = field(default_factory=list)


@dataclass
class GlobalStatement(ASTNode):
    names: list[str] = field(default_factory=list)


@dataclass
class NonlocalStatement(ASTNode):
    names: list[str] = field(default_factory=list)


@dataclass
class RaiseStatement(ASTNode):
    exception: ASTNode | None = None
    cause: ASTNode | None = None


@dataclass
class AssertStatement(ASTNode):
    test: ASTNode | None = None
    message: ASTNode | None = None


@dataclass
class ImportStatement(ASTNode):
    module: str = ""
    alias: str | None = None


@dataclass
class ImportFromStatement(ASTNode):
    module: str = ""
    names: list[tuple[str, str | None]] = field(default_factory=list)
    level: int = 0


@dataclass
class IfStatement(ASTNode):
    test: ASTNode | None = None
    body: list[ASTNode] = field(default_factory=list)
    elif_branches: list[tuple[ASTNode, list[ASTNode]]] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)


@dataclass
class WhileStatement(ASTNode):
    test: ASTNode | None = None
    body: list[ASTNode] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)


@dataclass
class ForStatement(ASTNode):
    target: ASTNode | None = None
    iterable: ASTNode | None = None
    body: list[ASTNode] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)
    is_async: bool = False


@dataclass
class FunctionDefinition(ASTNode):
    name: str = ""
    parameters: list[ASTNode] = field(default_factory=list)
    body: list[ASTNode] = field(default_factory=list)
    decorators: list[ASTNode] = field(default_factory=list)
    returns: ASTNode | None = None
    is_async: bool = False


@dataclass
class ClassDefinition(ASTNode):
    name: str = ""
    bases: list[ASTNode] = field(default_factory=list)
    body: list[ASTNode] = field(default_factory=list)
    decorators: list[ASTNode] = field(default_factory=list)


@dataclass
class TryStatement(ASTNode):
    body: list[ASTNode] = field(default_factory=list)
    handlers: list[ASTNode] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)
    finally_body: list[ASTNode] = field(default_factory=list)


@dataclass
class ExceptHandler(ASTNode):
    exception: ASTNode | None = None
    name: str | None = None
    body: list[ASTNode] = field(default_factory=list)
    is_star: bool = False


@dataclass
class WithStatement(ASTNode):
    items: list[tuple[ASTNode, ASTNode | None]] = field(default_factory=list)
    body: list[ASTNode] = field(default_factory=list)
    is_async: bool = False


@dataclass
class Parameter(ASTNode):
    name: str = ""
    kind: str = "normal"
    default: ASTNode | None = None
    annotation: ASTNode | None = None


# -------------------------
# Expressions
# -------------------------

@dataclass
class Identifier(ASTNode):
    name: str = ""


@dataclass
class Literal(ASTNode):
    value: Any = None


@dataclass
class BinaryOperation(ASTNode):
    left: ASTNode | None = None
    operator: str = ""
    right: ASTNode | None = None


@dataclass
class UnaryOperation(ASTNode):
    operator: str = ""
    operand: ASTNode | None = None


@dataclass
class BooleanOperation(ASTNode):
    left: ASTNode | None = None
    operator: str = ""
    right: ASTNode | None = None


@dataclass
class Comparison(ASTNode):
    left: ASTNode | None = None
    operators: list[str] = field(default_factory=list)
    comparators: list[ASTNode] = field(default_factory=list)


@dataclass
class NamedExpression(ASTNode):
    target: ASTNode | None = None
    value: ASTNode | None = None


@dataclass
class ConditionalExpression(ASTNode):
    value: ASTNode | None = None
    condition: ASTNode | None = None
    alternative: ASTNode | None = None


@dataclass
class CallExpression(ASTNode):
    function: ASTNode | None = None
    arguments: list[ASTNode] = field(default_factory=list)


@dataclass
class KeywordArgument(ASTNode):
    name: str = ""
    value: ASTNode | None = None


@dataclass
class AttributeAccess(ASTNode):
    object: ASTNode | None = None
    attribute: str = ""


@dataclass
class SubscriptExpression(ASTNode):
    value: ASTNode | None = None
    index: ASTNode | None = None


@dataclass
class SliceExpression(ASTNode):
    start: ASTNode | None = None
    stop: ASTNode | None = None
    step: ASTNode | None = None


@dataclass
class ListExpression(ASTNode):
    elements: list[ASTNode] = field(default_factory=list)


@dataclass
class TupleExpression(ASTNode):
    elements: list[ASTNode] = field(default_factory=list)


@dataclass
class SetExpression(ASTNode):
    elements: list[ASTNode] = field(default_factory=list)


@dataclass
class DictionaryExpression(ASTNode):
    entries: list[tuple[ASTNode | None, ASTNode]] = field(default_factory=list)


@dataclass
class ComprehensionExpression(ASTNode):
    element: ASTNode | None = None
    generators: list[ASTNode] = field(default_factory=list)


@dataclass
class ListComprehension(ComprehensionExpression):
    pass


@dataclass
class SetComprehension(ComprehensionExpression):
    pass


@dataclass
class GeneratorExpression(ComprehensionExpression):
    pass


@dataclass
class DictionaryComprehension(ComprehensionExpression):
    key: ASTNode | None = None


@dataclass
class Comprehension(ASTNode):
    target: ASTNode | None = None
    iterable: ASTNode | None = None
    conditions: list[ASTNode] = field(default_factory=list)
    is_async: bool = False


@dataclass
class LambdaExpression(ASTNode):
    parameters: list[ASTNode] = field(default_factory=list)
    body: ASTNode | None = None


@dataclass
class AwaitExpression(ASTNode):
    expression: ASTNode | None = None


@dataclass
class YieldExpression(ASTNode):
    value: ASTNode | None = None
    is_from: bool = False


@dataclass
class StarredExpression(ASTNode):
    value: ASTNode | None = None


@dataclass
class FStringExpression(ASTNode):
    value: str = ""
