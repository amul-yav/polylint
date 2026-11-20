"""Rule registry.

Rule modules (e.g. ``polylint.rules.python.naming``) register their
``Rule`` subclasses with :data:`default_registry` as a side effect of
being imported, using the :func:`register` decorator:

    @register
    class FunctionNamingRule(Rule):
        id = "PLN001"
        ...

The engine then asks the registry for rule *instances* (optionally
filtered by id, and with per-rule severity overrides) rather than
importing rule classes directly -- this is what "rules can be added
without changing the engine" means in practice.
"""

from __future__ import annotations

from typing import Iterable, Optional, TypeVar

from polylint.core.severity import Severity
from polylint.rules.base import Rule

RuleClass = TypeVar("RuleClass", bound=type[Rule])


class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, type[Rule]] = {}

    # ------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------

    def register(self, rule_cls: RuleClass) -> RuleClass:
        rule_id = getattr(rule_cls, "id", "")
        if not rule_id:
            raise ValueError(f"{rule_cls!r} must define a non-empty 'id'")
        existing = self._rules.get(rule_id)
        if existing is not None and existing is not rule_cls:
            raise ValueError(
                f"rule id {rule_id!r} is already registered by {existing!r}"
            )
        self._rules[rule_id] = rule_cls
        return rule_cls

    def unregister(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    def clear(self) -> None:
        self._rules.clear()

    # ------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------

    def get(self, rule_id: str) -> Optional[type[Rule]]:
        return self._rules.get(rule_id)

    def __contains__(self, rule_id: str) -> bool:
        return rule_id in self._rules

    def all_ids(self) -> list[str]:
        return sorted(self._rules)

    def all(self) -> list[type[Rule]]:
        return [self._rules[rule_id] for rule_id in self.all_ids()]

    def by_category(self, category: str) -> list[type[Rule]]:
        return [cls for cls in self.all() if cls.category == category]

    # ------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------

    def create(self, rule_id: str, severity: Optional[Severity] = None) -> Rule:
        cls = self.get(rule_id)
        if cls is None:
            raise KeyError(f"unknown rule id {rule_id!r}")
        return cls(severity=severity)

    def create_all(
        self,
        *,
        enabled_ids: Optional[Iterable[str]] = None,
        disabled_ids: Optional[Iterable[str]] = None,
        severities: Optional[dict[str, Severity]] = None,
    ) -> list[Rule]:
        """Instantiate every selected rule.

        ``enabled_ids`` restricts the set of rules to instantiate (default:
        every registered rule). ``disabled_ids`` removes rules from
        whatever set that leaves. ``severities`` maps a rule id to a
        severity override, applied on top of each rule's own default.
        """
        severities = severities or {}
        disabled = set(disabled_ids or ())
        ids = list(enabled_ids) if enabled_ids is not None else self.all_ids()

        rules: list[Rule] = []
        for rule_id in ids:
            if rule_id in disabled:
                continue
            cls = self.get(rule_id)
            if cls is None:
                raise KeyError(f"unknown rule id {rule_id!r}")
            rules.append(cls(severity=severities.get(rule_id)))
        return rules


default_registry = RuleRegistry()


def register(rule_cls: RuleClass) -> RuleClass:
    """Decorator: register ``rule_cls`` with the module-level default
    registry and return it unchanged."""
    return default_registry.register(rule_cls)