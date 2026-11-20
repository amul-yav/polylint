"""Importing this package registers every built-in Python lint rule
with :data:`polylint.rules.registry.default_registry`."""

from polylint.rules.python import naming  # noqa: F401
from polylint.rules.python import unused  # noqa: F401
from polylint.rules.python import imports  # noqa: F401
from polylint.rules.python import style  # noqa: F401

__all__ = ["naming", "unused", "imports", "style"]