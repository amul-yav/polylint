
from dataclasses import dataclass

import pytest

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity
from polylint.rules.base import Rule, RuleContext, walk


@dataclass
class Node:
    line: int
    column: int


@dataclass
class Parent:
    child: Node
    children: list[Node]


def test_walk_single_node():
    node = Node(1, 1)

    result = list(walk(node))

    assert result == [node]


def test_walk_nested_nodes():
    child = Node(2, 3)
    parent = Parent(
        child=child,
        children=[],
    )

    result = list(walk(parent))

    assert result == [parent, child]


def test_walk_list_children():
    first = Node(1, 1)
    second = Node(2, 1)

    parent = Parent(
        child=first,
        children=[second],
    )

    result = list(walk(parent))

    assert result == [parent, first, second]


def test_walk_tuple_children():
    first = Node(1, 1)
    second = Node(2, 1)

    result = list(walk((first, second)))

    assert result == [first, second]


def test_walk_nested_lists_and_tuples():
    first = Node(1, 1)
    second = Node(2, 1)

    result = list(walk([[first, (second,)]]))

    assert result == [first, second]


def test_walk_none():
    assert list(walk(None)) == []


def test_walk_primitive():
    assert list(walk("hello")) == []


def test_rule_context_creation():
    context = RuleContext(
        tree=None,
        source="x = 10",
        file_path="main.py",
    )

    assert context.tree is None
    assert context.source == "x = 10"
    assert context.file_path == "main.py"


def test_rule_context_default_path():
    context = RuleContext(tree=None, source="")

    assert context.file_path == "<module>"


def test_rule_context_lines():
    context = RuleContext(
        tree=None,
        source="x = 1\ny = 2\nz = 3",
    )

    assert context.lines == [
        "x = 1",
        "y = 2",
        "z = 3",
    ]


def test_rule_context_lines_cached():
    context = RuleContext(tree=None, source="x = 1")

    first = context.lines
    second = context.lines

    assert first is second


def test_rule_context_cached_computation():
    context = RuleContext(tree=None, source="")

    calls = []

    def compute():
        calls.append(1)
        return 42

    first = context.cached("answer", compute)
    second = context.cached("answer", compute)

    assert first == 42
    assert second == 42
    assert len(calls) == 1


def test_rule_context_different_cache_keys():
    context = RuleContext(tree=None, source="")

    assert context.cached("a", lambda: 1) == 1
    assert context.cached("b", lambda: 2) == 2


class ExampleRule(Rule):
    id = "PL001"
    name = "Example rule"
    description = "An example rule"
    category = "general"
    default_severity = Severity.WARNING

    def check(self, context):
        return []


def test_rule_metadata():
    rule = ExampleRule()

    assert rule.id == "PL001"
    assert rule.name == "Example rule"
    assert rule.description == "An example rule"
    assert rule.category == "general"


def test_rule_default_severity():
    rule = ExampleRule()

    assert rule.severity is Severity.WARNING


def test_rule_custom_severity():
    rule = ExampleRule(severity=Severity.ERROR)

    assert rule.severity is Severity.ERROR


def test_rule_enabled_by_default():
    rule = ExampleRule()

    assert rule.enabled is True


def test_rule_can_be_disabled():
    rule = ExampleRule(enabled=False)

    assert rule.enabled is False


def test_rule_diagnostic():
    rule = ExampleRule()

    diagnostic = rule.diagnostic(
        message="Something went wrong",
        line=4,
        column=2,
    )

    assert isinstance(diagnostic, Diagnostic)
    assert diagnostic.rule_id == "PL001"
    assert diagnostic.message == "Something went wrong"
    assert diagnostic.line == 4
    assert diagnostic.column == 2
    assert diagnostic.severity is Severity.WARNING


def test_rule_diagnostic_custom_severity():
    rule = ExampleRule(severity=Severity.ERROR)

    diagnostic = rule.diagnostic(
        message="Error",
        line=1,
        column=1,
    )

    assert diagnostic.severity is Severity.ERROR


def test_rule_diagnostic_for_node():
    rule = ExampleRule()
    node = Node(line=8, column=12)

    diagnostic = rule.diagnostic_for(
        "Problem found",
        node,
    )

    assert diagnostic.line == 8
    assert diagnostic.column == 12


def test_rule_diagnostic_extra_arguments():
    rule = ExampleRule()

    diagnostic = rule.diagnostic(
        message="Fix available",
        line=1,
        column=1,
        file_path="example.py",
        fixable=True,
    )

    assert diagnostic.file_path == "example.py"
    assert diagnostic.fixable is True


def test_rule_is_abstract():
    with pytest.raises(TypeError):
        Rule()
