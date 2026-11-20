"""Severity levels for diagnostics produced anywhere in PolyLint.

``Severity`` is an ``IntEnum`` so severities are directly orderable
(``Severity.WARNING < Severity.ERROR``), which makes "show me warnings
and above" filtering trivial: ``severity >= Severity.WARNING``.
"""

from __future__ import annotations

from enum import IntEnum


class Severity(IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2

    def __str__(self) -> str:
        return self.name.lower()

    @classmethod
    def from_string(cls, value: str) -> "Severity":
        try:
            return cls[value.strip().upper()]
        except KeyError as exc:
            valid = ", ".join(member.name.lower() for member in cls)
            raise ValueError(
                f"unknown severity {value!r}; expected one of: {valid}"
            ) from exc