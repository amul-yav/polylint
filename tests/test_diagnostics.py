
import pytest

from polylint.core.diagnostics import Diagnostic
from polylint.core.severity import Severity


def make_diagnostic(**kwargs):
    defaults = {
        "rule_id": "PL001",
        "message": "Undefined variable",
        "line": 3,
        "column": 5,
        "severity": Severity.ERROR,
    }
    defaults.update(kwargs)
    return Diagnostic(**defaults)


def test_diagnostic_creation():
    diagnostic = make_diagnostic()

    assert diagnostic.rule_id == "PL001"
    assert diagnostic.message == "Undefined variable"
    assert diagnostic.line == 3
    assert diagnostic.column == 5
    assert diagnostic.severity is Severity.ERROR


def test_default_file_path():
    diagnostic = make_diagnostic()

    assert diagnostic.file_path == "<module>"


def test_custom_file_path():
    diagnostic = make_diagnostic(file_path="main.py")

    assert diagnostic.file_path == "main.py"


def test_is_error():
    diagnostic = make_diagnostic(severity=Severity.ERROR)

    assert diagnostic.is_error is True
    assert diagnostic.is_warning is False


def test_is_warning():
    diagnostic = make_diagnostic(severity=Severity.WARNING)

    assert diagnostic.is_warning is True
    assert diagnostic.is_error is False


def test_info_is_not_error_or_warning():
    diagnostic = make_diagnostic(severity=Severity.INFO)

    assert diagnostic.is_error is False
    assert diagnostic.is_warning is False


def test_diagnostic_format():
    diagnostic = make_diagnostic(file_path="main.py")

    assert diagnostic.format() == (
        "main.py:3:5: PL001 [error] Undefined variable"
    )


def test_diagnostic_sort_key():
    diagnostic = make_diagnostic(
        file_path="main.py",
        line=10,
        column=4,
    )

    assert diagnostic.sort_key() == (
        "main.py", 10, 4, "PL001"
    )


def test_diagnostic_sorting():
    diagnostics = [
        make_diagnostic(line=10, column=1),
        make_diagnostic(line=2, column=5),
        make_diagnostic(line=2, column=1),
    ]

    result = sorted(diagnostics, key=lambda d: d.sort_key())

    assert [(d.line, d.column) for d in result] == [
        (2, 1),
        (2, 5),
        (10, 1),
    ]


def test_diagnostic_is_immutable():
    diagnostic = make_diagnostic()

    with pytest.raises(AttributeError):
        diagnostic.message = "Changed"


def test_optional_end_location():
    diagnostic = make_diagnostic(
        end_line=3,
        end_column=10,
    )

    assert diagnostic.end_line == 3
    assert diagnostic.end_column == 10


def test_fixable_default():
    diagnostic = make_diagnostic()

    assert diagnostic.fixable is False


def test_fixable_true():
    diagnostic = make_diagnostic(fixable=True)

    assert diagnostic.fixable is True
