from polylint.engine.rule_engine import RuleEngine
from polylint.fix.fixer import Fixer
from polylint.languages.python.lexer import Lexer
from polylint.languages.python.parser import Parser


def lint(source):
    tree = Parser(Lexer(source).tokenize()).parse()
    return RuleEngine(enabled_ids=["PLI001"]).run_with_fixes(tree, source)


def test_standalone_and_aliased_import_fixes_apply():
    for source in ("import os\n", "import os as operating_system\n"):
        diagnostics, fixes = lint(source)
        assert len(diagnostics) == len(fixes) == 1
        assert diagnostics[0].fixable
        assert Fixer().apply_fixes(source, fixes) == ""


def test_used_import_is_left_untouched():
    source = "import os\nprint(os.name)\n"
    diagnostics, fixes = lint(source)
    assert not diagnostics
    assert not fixes
    assert Fixer().apply_fixes(source, fixes) == source


def test_from_import_and_trailing_comment_are_preserved():
    source = "from os import path as os_path  # keep this\n"
    diagnostics, fixes = lint(source)
    assert len(diagnostics) == len(fixes) == 1
    assert Fixer().apply_fixes(source, fixes) == "# keep this\n"


def test_multiple_imports_on_one_line_are_not_fixed():
    source = "import os, sys\nprint(os.name)\n"
    diagnostics, fixes = lint(source)
    assert len(diagnostics) == 1
    assert not diagnostics[0].fixable
    assert not fixes
    assert Fixer().apply_fixes(source, fixes) == source


def test_multiple_from_import_names_are_not_fixed():
    source = "from os import path, name\nprint(path)\n"
    diagnostics, fixes = lint(source)
    assert len(diagnostics) == 1
    assert not diagnostics[0].fixable
    assert not fixes


def test_ambiguous_or_invalid_position_does_not_produce_fix():
    source = "import os\n"
    tree = Parser(Lexer(source).tokenize()).parse()
    # A malformed AST location cannot be mapped to verified source text.
    tree.body[0].line = 3
    diagnostics, fixes = RuleEngine(enabled_ids=["PLI001"]).run_with_fixes(tree, source)
    assert diagnostics
    assert not any(d.fixable for d in diagnostics)
    assert not fixes


def test_indented_import_comment_whitespace_is_preserved():
    source = "if True:\n    import os   # retained\n"
    diagnostics, fixes = lint(source)
    assert diagnostics and fixes
    assert Fixer().apply_fixes(source, fixes) == "if True:\n    # retained\n"
