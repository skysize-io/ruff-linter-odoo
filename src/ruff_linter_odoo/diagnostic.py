"""Diagnostic system for ruff-linter-odoo."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DiagnosticLevel(Enum):
    """Diagnostic severity levels matching Ruff's system."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    CONVENTION = "convention"
    REFACTOR = "refactor"


@dataclass
class Diagnostic:
    """Represents a linting diagnostic/violation."""

    code: str  # e.g., "OCA001"
    message: str
    filename: str
    line: int
    column: int
    level: DiagnosticLevel
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    fix_available: bool = False

    def to_dict(self):
        """Convert diagnostic to dictionary for JSON output."""
        return {
            "code": self.code,
            "message": self.message,
            "filename": self.filename,
            "location": {
                "row": self.line,
                "column": self.column,
            },
            "end_location": {
                "row": self.end_line or self.line,
                "column": self.end_column or self.column,
            }
            if self.end_line or self.end_column
            else None,
            "level": self.level.value,
            "fix": {"available": self.fix_available},
        }

    def __str__(self):
        """Return a Ruff-compatible string representation."""
        return f"{self.filename}:{self.line}:{self.column}: {self.code} {self.message}"
