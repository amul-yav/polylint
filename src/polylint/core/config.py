
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from polylint.core.severity import Severity


class ConfigError(Exception):
    """Raised when the PolyLint configuration is invalid."""


@dataclass
class PolyLintConfig:
    """Main configuration for PolyLint."""

    enabled_rules: dict[str, bool] = field(default_factory=dict)
    rule_severities: dict[str, Severity] = field(default_factory=dict)

    exclude: list[str] = field(default_factory=list)

    indent_size: int = 4
    max_line_length: int = 88
    final_newline: bool = True
    remove_trailing_whitespace: bool = True

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.indent_size, int) or isinstance(
            self.indent_size, bool
        ) or self.indent_size < 1:
            raise ConfigError("indent_size must be a positive integer")

        if not isinstance(self.max_line_length, int) or isinstance(
            self.max_line_length, bool
        ) or self.max_line_length < 1:
            raise ConfigError(
                "max_line_length must be a positive integer"
            )

        if not isinstance(self.final_newline, bool):
            raise ConfigError("final_newline must be a boolean")

        if not isinstance(self.remove_trailing_whitespace, bool):
            raise ConfigError(
                "remove_trailing_whitespace must be a boolean"
            )

        if not isinstance(self.exclude, list) or not all(
            isinstance(item, str) for item in self.exclude
        ):
            raise ConfigError("exclude must be a list of strings")

        if not isinstance(self.enabled_rules, dict):
            raise ConfigError("enabled_rules must be a dictionary")

        for rule_id, enabled in self.enabled_rules.items():
            if not isinstance(rule_id, str) or not isinstance(
                enabled, bool
            ):
                raise ConfigError(
                    "enabled_rules must map rule IDs to booleans"
                )

        if not isinstance(self.rule_severities, dict):
            raise ConfigError("rule_severities must be a dictionary")

        for rule_id, severity in self.rule_severities.items():
            if not isinstance(rule_id, str):
                raise ConfigError("rule IDs must be strings")

            if not isinstance(severity, Severity):
                raise ConfigError(
                    f"invalid severity for rule {rule_id!r}"
                )

    def is_rule_enabled(self, rule_id: str) -> bool:
        """Return whether a rule is enabled."""

        return self.enabled_rules.get(rule_id, True)

    def get_rule_severity(
        self,
        rule_id: str,
        default: Severity = Severity.WARNING,
    ) -> Severity:
        """Return configured severity or the supplied default."""

        return self.rule_severities.get(rule_id, default)

    def is_excluded(self, path: str | Path) -> bool:
        """Check whether a path matches an exclusion pattern."""

        from fnmatch import fnmatch

        path = str(path)

        for pattern in self.exclude:
            if fnmatch(path, pattern):
                return True

            if fnmatch(Path(path).name, pattern):
                return True

        return False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolyLintConfig:
        """Create configuration from a dictionary."""

        if not isinstance(data, dict):
            raise ConfigError("configuration must be a dictionary")

        # Accept either a direct PolyLint configuration or a
        # pyproject.toml-style configuration.
        if "tool" in data:
            tool = data["tool"]

            if not isinstance(tool, dict):
                raise ConfigError("'tool' must be a table")

            data = tool.get("polylint", {})

        if not isinstance(data, dict):
            raise ConfigError("'polylint' must be a table")

        rules = data.get("rules", {})
        formatting = data.get("format", {})

        if not isinstance(rules, dict):
            raise ConfigError("'rules' must be a table")

        if not isinstance(formatting, dict):
            raise ConfigError("'format' must be a table")

        enabled_rules = rules.get("enabled", {})
        disabled_rules = rules.get("disabled", [])
        severities = rules.get("severity", {})

        if not isinstance(enabled_rules, dict):
            raise ConfigError("'rules.enabled' must be a table")

        if not isinstance(disabled_rules, list) or not all(
            isinstance(item, str) for item in disabled_rules
        ):
            raise ConfigError("'rules.disabled' must be a list of strings")

        if not isinstance(severities, dict):
            raise ConfigError("'rules.severity' must be a table")

        enabled = dict(enabled_rules)

        for rule_id in disabled_rules:
            if rule_id in enabled and enabled[rule_id] is True:
                raise ConfigError(
                    f"rule {rule_id!r} cannot be both enabled and disabled"
                )
            enabled[rule_id] = False

        parsed_severities: dict[str, Severity] = {}

        for rule_id, value in severities.items():
            if not isinstance(value, str):
                raise ConfigError(
                    f"severity for {rule_id!r} must be a string"
                )

            try:
                parsed_severities[rule_id] = Severity.from_string(value)
            except ValueError as exc:
                raise ConfigError(str(exc)) from exc

        exclude = data.get("exclude", [])

        if not isinstance(exclude, list):
            raise ConfigError("'exclude' must be a list")

        return cls(
            enabled_rules=enabled,
            rule_severities=parsed_severities,
            exclude=exclude,
            indent_size=formatting.get("indent_size", 4),
            max_line_length=formatting.get("max_line_length", 88),
            final_newline=formatting.get("final_newline", True),
            remove_trailing_whitespace=formatting.get(
                "remove_trailing_whitespace", True
            ),
        )

    @classmethod
    def from_toml(cls, content: str) -> PolyLintConfig:
        """Load configuration from TOML text."""

        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"invalid TOML: {exc}") from exc

        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: str | Path) -> PolyLintConfig:
        """Load configuration from a TOML file."""

        path = Path(path)

        try:
            with path.open("rb") as file:
                data = tomllib.load(file)
        except FileNotFoundError as exc:
            raise ConfigError(
                f"configuration file not found: {path}"
            ) from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"invalid TOML: {exc}") from exc
        except OSError as exc:
            raise ConfigError(
                f"cannot read configuration file: {exc}"
            ) from exc

        return cls.from_dict(data)
