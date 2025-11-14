"""ruff-linter-odoo: A modern, standalone linting tool for Odoo modules."""

__version__ = "1.0.0"

from .linter import Linter
from .diagnostic import Diagnostic, DiagnosticLevel

__all__ = ["Linter", "Diagnostic", "DiagnosticLevel", "__version__"]
