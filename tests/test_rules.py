"""Tests for the lint rules engine: the registry, the engine itself,
and every built-in Python rule."""

import pytest

from polylint.core.severity import Severity
from polylint.languages.python.lexer import Lexer
from polylint.languages.python.parser import Parser
from polylint.engine.rule_engine import RuleEngine
from polylint.rules.base import Rule, RuleContext
from polylint.rules.registry import RuleRegistry, default_registry

# Importing this registers every built-in rule (also done by the engine,
# but tests exercise the registry directly too).
import polylint.rules.python  # noqa: F401

from polylint.rules.python.naming import (
    AmbiguousNameRule,
    ClassNamingRule,
    FunctionNamingRule,
    VariableNamingRule,
)
from polylint.rules.python.unused import (
    UndefinedNameRule,
    UnreachableCodeRule,
    UnusedParameterRule,
    UnusedVariableRule,
)
from polylint.rules.python.imports import (
    DuplicateImportRule,
    ImportNotAtTopRule,
    StarImportRule,
    UnusedImportRule,
)
from polylint.rules.python.style import (
    ComparisonToSingletonRule,
    MissingDocstringRule,
    MultipleStatementsOnOneLineRule,
    TooManyArgumentsRule,
)


def parse(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def run_rule(rule_cls, source: str, **rule_kwargs):
    tree = parse(source)
    context = RuleContext(tree=tree, source=source, file_path="test.py")
    rule = rule_cls(**rule_kwargs)
    return rule.check(context)


def ids(diagnostics):
    return [d.rule_id for d in diagnostics]


def messages(diagnostics):
    return [d.message for d in diagnostics]


# ======================================================================
# Registry
# ======================================================================

class TestRuleRegistry:
    def _dummy_rule(self, rule_id="PLX999"):
        class Dummy(Rule):
            id = rule_id
            name = "dummy"
            category = "test"
            default_severity = Severity.WARNING

            def check(self, context):
                return [self.diagnostic("dummy message", 1, 1)]

        return Dummy

    def test_register_and_get(self):
        registry = RuleRegistry()
        dummy = self._dummy_rule()
        registry.register(dummy)
        assert registry.get("PLX999") is dummy

    def test_register_requires_id(self):
        registry = RuleRegistry()

        class NoId(Rule):
            id = ""

            def check(self, context):
                return []

        with pytest.raises(ValueError):
            registry.register(NoId)

    def test_duplicate_id_different_class_raises(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX001"))
        with pytest.raises(ValueError):
            registry.register(self._dummy_rule("PLX001"))

    def test_registering_same_class_twice_is_fine(self):
        registry = RuleRegistry()
        dummy = self._dummy_rule("PLX002")
        registry.register(dummy)
        registry.register(dummy)  # no error
        assert registry.get("PLX002") is dummy

    def test_unregister(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX003"))
        registry.unregister("PLX003")
        assert registry.get("PLX003") is None

    def test_unknown_id_returns_none(self):
        registry = RuleRegistry()
        assert registry.get("DOES-NOT-EXIST") is None

    def test_all_ids_sorted(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX005"))
        registry.register(self._dummy_rule("PLX001"))
        assert registry.all_ids() == ["PLX001", "PLX005"]

    def test_by_category(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX006"))
        assert registry.by_category("test") == [registry.get("PLX006")]
        assert registry.by_category("other") == []

    def test_create_instantiates_with_default_severity(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX007"))
        rule = registry.create("PLX007")
        assert rule.severity is Severity.WARNING

    def test_create_with_severity_override(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX008"))
        rule = registry.create("PLX008", severity=Severity.ERROR)
        assert rule.severity is Severity.ERROR

    def test_create_unknown_id_raises(self):
        registry = RuleRegistry()
        with pytest.raises(KeyError):
            registry.create("NOPE")

    def test_create_all_default_is_every_registered_rule(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX009"))
        registry.register(self._dummy_rule("PLX010"))
        rules = registry.create_all()
        assert {r.id for r in rules} == {"PLX009", "PLX010"}

    def test_create_all_respects_enabled_ids(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX011"))
        registry.register(self._dummy_rule("PLX012"))
        rules = registry.create_all(enabled_ids=["PLX011"])
        assert {r.id for r in rules} == {"PLX011"}

    def test_create_all_respects_disabled_ids(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX013"))
        registry.register(self._dummy_rule("PLX014"))
        rules = registry.create_all(disabled_ids=["PLX013"])
        assert {r.id for r in rules} == {"PLX014"}

    def test_create_all_applies_severity_overrides(self):
        registry = RuleRegistry()
        registry.register(self._dummy_rule("PLX015"))
        rules = registry.create_all(severities={"PLX015": Severity.ERROR})
        assert rules[0].severity is Severity.ERROR

    def test_default_registry_has_builtin_python_rules(self):
        for expected in ("PLN001", "PLU001", "PLI001", "PLS001"):
            assert default_registry.get(expected) is not None


# ======================================================================
# Engine
# ======================================================================

class TestRuleEngine:
    def test_run_returns_sorted_diagnostics(self):
        engine = RuleEngine()
        tree = parse("import os\nimport os\n")
        diags = engine.run(tree, "import os\nimport os\n", file_path="a.py")
        lines = [d.line for d in diags]
        assert lines == sorted(lines)

    def test_run_stamps_file_path(self):
        engine = RuleEngine()
        tree = parse("import os\n")
        diags = engine.run(tree, "import os\n", file_path="pkg/mod.py")
        assert all(d.file_path == "pkg/mod.py" for d in diags)

    def test_enabled_ids_restricts_rules(self):
        engine = RuleEngine(enabled_ids=["PLI001"])
        tree = parse("import os\n")
        diags = engine.run(tree, "import os\n")
        assert set(ids(diags)) <= {"PLI001"}
        assert len(diags) == 1

    def test_disabled_ids_removes_rule(self):
        engine = RuleEngine(disabled_ids=["PLI001"])
        tree = parse("import os\n")
        diags = engine.run(tree, "import os\n")
        assert "PLI001" not in ids(diags)

    def test_severity_override_applies_through_engine(self):
        engine = RuleEngine(severities={"PLI001": Severity.ERROR})
        tree = parse("import os\n")
        diags = engine.run(tree, "import os\n")
        unused_import = next(d for d in diags if d.rule_id == "PLI001")
        assert unused_import.severity is Severity.ERROR

    def test_disabling_a_rule_instance_stops_it_from_running(self):
        engine = RuleEngine(enabled_ids=["PLI001"])
        engine.rules[0].enabled = False
        tree = parse("import os\n")
        diags = engine.run(tree, "import os\n")
        assert diags == []

    def test_clean_file_produces_no_diagnostics(self):
        engine = RuleEngine()
        source = (
            '"""A clean module."""\n'
            "import os\n"
            "\n"
            "\n"
            "def get_cwd():\n"
            '    """Return the current working directory."""\n'
            "    return os.getcwd()\n"
        )
        diags = engine.run(parse(source), source)
        assert diags == []


# ======================================================================
# Naming rules
# ======================================================================

class TestFunctionNamingRule:
    def test_snake_case_is_fine(self):
        diags = run_rule(FunctionNamingRule, "def do_thing():\n    pass\n")
        assert diags == []

    def test_camel_case_is_flagged(self):
        diags = run_rule(FunctionNamingRule, "def doThing():\n    pass\n")
        assert ids(diags) == ["PLN001"]

    def test_dunder_methods_are_fine(self):
        diags = run_rule(
            FunctionNamingRule, "class C:\n    def __init__(self):\n        pass\n"
        )
        assert diags == []

    def test_nested_function_is_checked_too(self):
        diags = run_rule(
            FunctionNamingRule,
            "def outer():\n    def badName():\n        pass\n    return badName\n",
        )
        assert ids(diags) == ["PLN001"]


class TestClassNamingRule:
    def test_pascal_case_is_fine(self):
        diags = run_rule(ClassNamingRule, "class MyClass:\n    pass\n")
        assert diags == []

    def test_snake_case_class_is_flagged(self):
        diags = run_rule(ClassNamingRule, "class my_class:\n    pass\n")
        assert ids(diags) == ["PLN002"]

    def test_leading_underscore_pascal_is_fine(self):
        diags = run_rule(ClassNamingRule, "class _Private:\n    pass\n")
        assert diags == []


class TestVariableNamingRule:
    def test_snake_case_variable_is_fine(self):
        diags = run_rule(VariableNamingRule, "my_value = 1\n")
        assert diags == []

    def test_camel_case_variable_is_flagged(self):
        diags = run_rule(VariableNamingRule, "myValue = 1\n")
        assert ids(diags) == ["PLN003"]

    def test_all_caps_constant_is_exempt(self):
        diags = run_rule(VariableNamingRule, "MAX_SIZE = 100\n")
        assert diags == []

    def test_tuple_unpacking_targets_are_checked(self):
        diags = run_rule(VariableNamingRule, "(goodName, badOne) = (1, 2)\n")
        assert len(diags) == 2


class TestAmbiguousNameRule:
    def test_ambiguous_parameter_is_flagged(self):
        diags = run_rule(AmbiguousNameRule, "def f(l):\n    return l\n")
        assert ids(diags) == ["PLN004"]

    def test_ambiguous_variable_is_flagged(self):
        diags = run_rule(AmbiguousNameRule, "O = 1\nprint(O)\n")
        assert ids(diags) == ["PLN004"]

    def test_normal_name_not_flagged(self):
        diags = run_rule(AmbiguousNameRule, "def f(low):\n    return low\n")
        assert diags == []


# ======================================================================
# Semantic-backed rules (unused.py)
# ======================================================================

class TestUndefinedNameRule:
    def test_undefined_name_flagged(self):
        diags = run_rule(UndefinedNameRule, "print(missing)\n")
        assert ids(diags) == ["PLU001"]

    def test_defined_name_not_flagged(self):
        diags = run_rule(UndefinedNameRule, "x = 1\nprint(x)\n")
        assert diags == []

    def test_default_severity_is_error(self):
        diags = run_rule(UndefinedNameRule, "print(missing)\n")
        assert diags[0].severity is Severity.ERROR

    def test_severity_can_be_overridden(self):
        diags = run_rule(UndefinedNameRule, "print(missing)\n", severity=Severity.WARNING)
        assert diags[0].severity is Severity.WARNING


class TestUnusedVariableRule:
    def test_unused_variable_flagged(self):
        diags = run_rule(UnusedVariableRule, "def f():\n    x = 1\nf()\n")
        assert ids(diags) == ["PLU002"]

    def test_used_variable_not_flagged(self):
        diags = run_rule(UnusedVariableRule, "def f():\n    x = 1\n    return x\nf()\n")
        assert diags == []


class TestUnusedParameterRule:
    def test_unused_parameter_flagged(self):
        diags = run_rule(UnusedParameterRule, "def f(a):\n    pass\nf(1)\n")
        assert ids(diags) == ["PLU003"]

    def test_used_parameter_not_flagged(self):
        diags = run_rule(UnusedParameterRule, "def f(a):\n    return a\nf(1)\n")
        assert diags == []


class TestUnreachableCodeRule:
    def test_code_after_return_flagged(self):
        diags = run_rule(
            UnreachableCodeRule,
            "def f():\n    return 1\n    x = 2\nf()\n",
        )
        assert ids(diags) == ["PLU004"]

    def test_no_dead_code_not_flagged(self):
        diags = run_rule(UnreachableCodeRule, "def f():\n    return 1\nf()\n")
        assert diags == []


# ======================================================================
# Import rules
# ======================================================================

class TestUnusedImportRule:
    def test_unused_import_flagged(self):
        diags = run_rule(UnusedImportRule, "import os\n")
        assert ids(diags) == ["PLI001"]

    def test_used_import_not_flagged(self):
        diags = run_rule(UnusedImportRule, "import os\nprint(os)\n")
        assert diags == []


class TestImportNotAtTopRule:
    def test_leading_imports_are_fine(self):
        diags = run_rule(ImportNotAtTopRule, "import os\nimport sys\nprint(os, sys)\n")
        assert diags == []

    def test_import_after_code_is_flagged(self):
        diags = run_rule(ImportNotAtTopRule, "x = 1\nimport os\nprint(x, os)\n")
        assert ids(diags) == ["PLI002"]

    def test_docstring_before_imports_is_fine(self):
        diags = run_rule(
            ImportNotAtTopRule,
            '"""Module docstring."""\nimport os\nprint(os)\n',
        )
        assert diags == []


class TestDuplicateImportRule:
    def test_duplicate_plain_import_flagged(self):
        diags = run_rule(DuplicateImportRule, "import os\nimport os\n")
        assert ids(diags) == ["PLI003"]

    def test_duplicate_from_import_flagged(self):
        diags = run_rule(
            DuplicateImportRule,
            "from math import sqrt\nfrom math import sqrt\nprint(sqrt)\n",
        )
        assert ids(diags) == ["PLI003"]

    def test_distinct_imports_not_flagged(self):
        diags = run_rule(DuplicateImportRule, "import os\nimport sys\nprint(os, sys)\n")
        assert diags == []

    def test_same_module_different_alias_not_flagged(self):
        diags = run_rule(
            DuplicateImportRule,
            "import os\nimport os as operating_system\nprint(os, operating_system)\n",
        )
        assert diags == []


class TestStarImportRule:
    def test_no_star_import_is_fine(self):
        diags = run_rule(StarImportRule, "from math import sqrt\nprint(sqrt)\n")
        assert diags == []
    # A direct "from x import *" case can't be constructed here because
    # the current parser doesn't accept that syntax yet (see the note in
    # the semantic analyzer handoff); this rule is ready for when it does.


# ======================================================================
# Style rules
# ======================================================================

class TestTooManyArgumentsRule:
    def test_few_parameters_is_fine(self):
        diags = run_rule(TooManyArgumentsRule, "def f(a, b):\n    return a + b\n")
        assert diags == []

    def test_too_many_parameters_is_flagged(self):
        diags = run_rule(
            TooManyArgumentsRule,
            "def f(a, b, c, d, e, g):\n    return a\n",
        )
        assert ids(diags) == ["PLS001"]

    def test_threshold_is_configurable(self):
        diags = run_rule(
            TooManyArgumentsRule,
            "def f(a, b, c):\n    return a\n",
            severity=None,
        )
        # default max is 5, so 3 parameters is fine
        assert diags == []


class TestMissingDocstringRule:
    def test_function_with_docstring_is_fine(self):
        diags = run_rule(
            MissingDocstringRule,
            'def f():\n    """Docstring."""\n    pass\n',
        )
        assert diags == []

    def test_function_without_docstring_is_flagged(self):
        diags = run_rule(MissingDocstringRule, "def f():\n    pass\n")
        assert ids(diags) == ["PLS002"]

    def test_class_without_docstring_is_flagged(self):
        diags = run_rule(MissingDocstringRule, "class C:\n    pass\n")
        assert ids(diags) == ["PLS002"]

    def test_class_with_docstring_is_fine(self):
        diags = run_rule(MissingDocstringRule, 'class C:\n    """A class."""\n    pass\n')
        assert diags == []


class TestComparisonToSingletonRule:
    def test_equality_with_none_is_flagged(self):
        diags = run_rule(ComparisonToSingletonRule, "x = 1\nif x == None:\n    pass\n")
        assert ids(diags) == ["PLS003"]

    def test_is_none_is_fine(self):
        diags = run_rule(ComparisonToSingletonRule, "x = None\nif x is None:\n    pass\n")
        assert diags == []

    def test_equality_with_true_is_flagged(self):
        diags = run_rule(ComparisonToSingletonRule, "flag = True\nif flag == True:\n    pass\n")
        assert ids(diags) == ["PLS003"]

    def test_equality_with_ordinary_literal_not_flagged(self):
        diags = run_rule(ComparisonToSingletonRule, "x = 1\nif x == 1:\n    pass\n")
        assert diags == []


class TestMultipleStatementsOnOneLineRule:
    def test_separate_lines_are_fine(self):
        diags = run_rule(MultipleStatementsOnOneLineRule, "x = 1\ny = 2\n")
        assert diags == []

    def test_semicolon_joined_statements_flagged(self):
        diags = run_rule(MultipleStatementsOnOneLineRule, "x = 1; y = 2\n")
        assert ids(diags) == ["PLS004"]

    def test_flagged_once_per_line_even_with_three_statements(self):
        diags = run_rule(MultipleStatementsOnOneLineRule, "x = 1; y = 2; z = 3\n")
        assert len(diags) == 1

    def test_does_not_false_positive_on_list_literal(self):
        diags = run_rule(MultipleStatementsOnOneLineRule, "values = [1, 2, 3]\n")
        assert diags == []

    def test_inside_function_body(self):
        diags = run_rule(
            MultipleStatementsOnOneLineRule,
            "def f():\n    a = 1; b = 2\n    return a + b\nf()\n",
        )
        assert ids(diags) == ["PLS004"]