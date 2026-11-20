
import pytest

from polylint.core.severity import Severity


def test_severity_values():
    assert Severity.INFO == 0
    assert Severity.WARNING == 1
    assert Severity.ERROR == 2


def test_severity_ordering():
    assert Severity.INFO < Severity.WARNING
    assert Severity.WARNING < Severity.ERROR


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        (Severity.INFO, "info"),
        (Severity.WARNING, "warning"),
        (Severity.ERROR, "error"),
    ],
)
def test_severity_string(severity, expected):
    assert str(severity) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("info", Severity.INFO),
        ("INFO", Severity.INFO),
        (" warning ", Severity.WARNING),
        ("Error", Severity.ERROR),
    ],
)
def test_from_string_valid(value, expected):
    assert Severity.from_string(value) is expected


@pytest.mark.parametrize(
    "value",
    ["", "debug", "fatal", "unknown", "trace"],
)
def test_from_string_invalid(value):
    with pytest.raises(ValueError):
        Severity.from_string(value)


def test_invalid_severity_message():
    with pytest.raises(ValueError, match="unknown severity"):
        Severity.from_string("debug")
