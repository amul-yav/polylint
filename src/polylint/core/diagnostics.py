"""The canonical diagnostic type produced by PolyLint's rules and engine.

Every :class:`~polylint.rules.base.Rule` reports problems as
:class:`Diagnostic` instances; the engine just collects, sorts and
(eventually) formats them. This is deliberately independent from
:class:`polylint.languages.python.semantic.Diagnostic`, which is an
internal detail of the semantic analyzer -- rules that rely on the
semantic analyzer translate its findings into *these* diagnostics,
under their own rule id and severity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from polylint.core.severity import Severity


@dataclass(frozen=True)
class Diagnostic:
    rule_id: str
    message: str
    line: int
    column: int
    severity: Severity
    file_path: str = "<module>"
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    fixable: bool = False

    @property
    def is_error(self) -> bool:
        return self.severity is Severity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity is Severity.WARNING

    def format(self) -> str:
        """A single-line, editor/terminal friendly rendering."""
        return (
            f"{self.file_path}:{self.line}:{self.column}: "
            f"{self.rule_id} [{self.severity}] {self.message}"
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return self.format()

    def sort_key(self) -> tuple:
        return (self.file_path, self.line, self.column, self.rule_id)