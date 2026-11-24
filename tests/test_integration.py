
from polylint.languages.python.lexer import Lexer
from polylint.languages.python.parser import Parser
from polylint.engine.rule_engine import RuleEngine


def analyze_source(source):
    """Run Python source through the analysis pipeline."""
    tokens = Lexer(source).tokenize()
    tree = Parser(tokens).parse()

    engine = RuleEngine()
    diagnostics = engine.run(tree, source)

    return tree, diagnostics


def test_valid_python_code():
    source = """
def add(a, b):
    return a + b
"""

    tree, diagnostics = analyze_source(source)

    assert tree is not None
    assert isinstance(diagnostics, list)


def test_detects_naming_violation():
    source = """
def calculateTotal(Price):
    return Price
"""

    _, diagnostics = analyze_source(source)

    rule_ids = [diagnostic.rule_id for diagnostic in diagnostics]

    assert any(rule_id.startswith("PLN") for rule_id in rule_ids)


def test_detects_unused_variable():
    source = """
def calculate():
    unused_variable = 100
    return 10
"""

    _, diagnostics = analyze_source(source)

    rule_ids = [diagnostic.rule_id for diagnostic in diagnostics]

    assert any(rule_id.startswith("PLU") for rule_id in rule_ids)


def test_detects_import_issue():
    source = """
import os

def calculate():
    return 10
"""

    _, diagnostics = analyze_source(source)

    rule_ids = [diagnostic.rule_id for diagnostic in diagnostics]

    assert any(rule_id.startswith("PLI") for rule_id in rule_ids)


def test_multiple_violations():
    source = """
import os

def calculateTotal(Price):
    unused_variable = 100
    return Price
"""

    _, diagnostics = analyze_source(source)

    assert len(diagnostics) >= 2


def test_clean_code():
    source = """
def calculate_total(price, quantity):
    total = price * quantity
    return total
"""

    _, diagnostics = analyze_source(source)

    assert isinstance(diagnostics, list)


def test_diagnostics_have_valid_locations():
    source = """
def calculateTotal(Price):
    return Price
"""

    _, diagnostics = analyze_source(source)

    for diagnostic in diagnostics:
        assert diagnostic.line >= 1
        assert diagnostic.column >= 1
        assert diagnostic.rule_id
        assert diagnostic.message


def test_empty_source():
    source = ""

    tree, diagnostics = analyze_source(source)

    assert tree is not None
    assert isinstance(diagnostics, list)
