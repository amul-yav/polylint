
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class FixError(Exception):
    """Raised when a fix cannot be safely applied."""


@dataclass(frozen=True)
class TextEdit:
    """Represents a replacement in source code."""

    start: int
    end: int
    replacement: str

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("start cannot be negative")

        if self.end < self.start:
            raise ValueError("end cannot be before start")


@dataclass(frozen=True)
class Fix:
    """A collection of text edits representing one automatic fix."""

    rule_id: str
    message: str
    edits: tuple[TextEdit, ...]

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("rule_id cannot be empty")

        if not self.edits:
            raise ValueError("a fix must contain at least one edit")


class Fixer:
    """Safely applies automatic fixes to source code."""

    @staticmethod
    def _validate_edit(edit: TextEdit, source_length: int) -> None:
        if edit.end > source_length:
            raise FixError(
                f"edit range {edit.start}:{edit.end} exceeds "
                f"source length {source_length}"
            )

    @staticmethod
    def _validate_conflicts(edits: list[TextEdit]) -> None:
        ordered = sorted(edits, key=lambda edit: (edit.start, edit.end))

        for previous, current in zip(ordered, ordered[1:]):
            if current.start < previous.end:
                raise FixError(
                    f"overlapping edits: "
                    f"{previous.start}:{previous.end} and "
                    f"{current.start}:{current.end}"
                )

            if (
                current.start == previous.start
                and current.end == previous.end
            ):
                raise FixError("duplicate edits are not allowed")

    def apply_edits(
        self,
        source: str,
        edits: Iterable[TextEdit],
    ) -> str:
        """Apply a collection of edits to source code."""

        edits = list(edits)

        for edit in edits:
            self._validate_edit(edit, len(source))

        self._validate_conflicts(edits)

        result = source

        for edit in sorted(
            edits,
            key=lambda item: (item.start, item.end),
            reverse=True,
        ):
            result = (
                result[:edit.start]
                + edit.replacement
                + result[edit.end:]
            )

        return result

    def apply_fix(self, source: str, fix: Fix) -> str:
        """Apply one fix."""

        return self.apply_edits(source, fix.edits)

    def apply_fixes(
        self,
        source: str,
        fixes: Iterable[Fix],
    ) -> str:
        """Apply multiple fixes together."""

        edits: list[TextEdit] = []

        for fix in fixes:
            edits.extend(fix.edits)

        return self.apply_edits(source, edits)
