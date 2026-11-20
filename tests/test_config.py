
import pytest

from polylint.core.config import (
    ConfigError,
    PolyLintConfig,
)
from polylint.core.severity import Severity


def test_default_config():
    config = PolyLintConfig()

    assert config.indent_size == 4
    assert config.max_line_length == 88
    assert config.final_newline is True
    assert config.remove_trailing_whitespace is True


def test_default_rules_enabled():
    config = PolyLintConfig()

    assert config.is_rule_enabled("PL001") is True


def test_disable_rule():
    config = PolyLintConfig(
        enabled_rules={"PL001": False}
    )

    assert config.is_rule_enabled("PL001") is False


def test_enable_rule():
    config = PolyLintConfig(
        enabled_rules={"PL001": True}
    )

    assert config.is_rule_enabled("PL001") is True


def test_default_severity():
    config = PolyLintConfig()

    assert config.get_rule_severity("PL001") == Severity.WARNING


def test_custom_severity():
    config = PolyLintConfig(
        rule_severities={"PL001": Severity.ERROR}
    )

    assert config.get_rule_severity("PL001") == Severity.ERROR


def test_custom_default_severity():
    config = PolyLintConfig()

    assert config.get_rule_severity(
        "PL001", Severity.INFO
    ) == Severity.INFO


def test_invalid_indent_size():
    with pytest.raises(ConfigError):
        PolyLintConfig(indent_size=0)


def test_invalid_max_line_length():
    with pytest.raises(ConfigError):
        PolyLintConfig(max_line_length=0)


def test_invalid_boolean_setting():
    with pytest.raises(ConfigError):
        PolyLintConfig(final_newline="yes")


def test_invalid_exclude():
    with pytest.raises(ConfigError):
        PolyLintConfig(exclude="*.py")


def test_invalid_enabled_rules():
    with pytest.raises(ConfigError):
        PolyLintConfig(enabled_rules={"PL001": "yes"})


def test_invalid_rule_severity():
    with pytest.raises(ConfigError):
        PolyLintConfig(rule_severities={"PL001": "error"})


def test_exclude_filename():
    config = PolyLintConfig(exclude=["*.pyc"])

    assert config.is_excluded("cache.pyc")


def test_exclude_path():
    config = PolyLintConfig(exclude=["build/*"])

    assert config.is_excluded("build/output.py")


def test_non_excluded_path():
    config = PolyLintConfig(exclude=["*.pyc"])

    assert config.is_excluded("main.py") is False


def test_from_dict():
    config = PolyLintConfig.from_dict({
        "format": {
            "indent_size": 2,
            "max_line_length": 100,
        }
    })

    assert config.indent_size == 2
    assert config.max_line_length == 100


def test_from_dict_rules():
    config = PolyLintConfig.from_dict({
        "rules": {
            "enabled": {
                "PL001": True,
            },
            "disabled": ["PL002"],
            "severity": {
                "PL001": "error",
            },
        }
    })

    assert config.is_rule_enabled("PL001") is True
    assert config.is_rule_enabled("PL002") is False
    assert config.get_rule_severity("PL001") == Severity.ERROR


def test_from_dict_exclude():
    config = PolyLintConfig.from_dict({
        "exclude": ["build/*", "*.pyc"],
    })

    assert config.is_excluded("main.pyc")


def test_from_dict_pyproject_structure():
    config = PolyLintConfig.from_dict({
        "tool": {
            "polylint": {
                "format": {
                    "indent_size": 2,
                }
            }
        }
    })

    assert config.indent_size == 2


def test_from_toml():
    content = """
[format]
indent_size = 2
max_line_length = 100
"""

    config = PolyLintConfig.from_toml(content)

    assert config.indent_size == 2
    assert config.max_line_length == 100


def test_from_toml_with_rules():
    content = """
[rules.enabled]
PL001 = true

[rules.severity]
PL001 = "error"

[rules]
disabled = ["PL002"]
"""

    config = PolyLintConfig.from_toml(content)

    assert config.is_rule_enabled("PL001") is True
    assert config.is_rule_enabled("PL002") is False
    assert config.get_rule_severity("PL001") == Severity.ERROR


def test_invalid_toml():
    with pytest.raises(ConfigError):
        PolyLintConfig.from_toml("invalid = [")


def test_from_dict_invalid_root():
    with pytest.raises(ConfigError):
        PolyLintConfig.from_dict([])


def test_from_file(tmp_path):
    path = tmp_path / "polylint.toml"

    path.write_text(
        """
[format]
indent_size = 2
""",
        encoding="utf-8",
    )

    config = PolyLintConfig.from_file(path)

    assert config.indent_size == 2


def test_missing_file():
    with pytest.raises(ConfigError):
        PolyLintConfig.from_file("missing.toml")


def test_conflicting_enabled_and_disabled_rules():
    with pytest.raises(ConfigError):
        PolyLintConfig.from_dict({
            "rules": {
                "enabled": {"PL001": True},
                "disabled": ["PL001"],
            }
        })
