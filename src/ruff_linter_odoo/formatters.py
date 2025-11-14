"""Output formatters for ruff-linter-odoo."""

import json
from typing import List

from .diagnostic import Diagnostic


class Formatter:
    """Base class for output formatters."""

    def format(self, diagnostics: List[Diagnostic]) -> str:
        """Format diagnostics for output."""
        raise NotImplementedError


class TextFormatter(Formatter):
    """Ruff-compatible text formatter."""

    def format(self, diagnostics: List[Diagnostic]) -> str:
        """Format diagnostics as text (similar to Ruff's default output)."""
        if not diagnostics:
            return ""

        lines = []
        for diag in sorted(diagnostics, key=lambda d: (d.filename, d.line, d.column)):
            lines.append(str(diag))

        # Add summary
        if diagnostics:
            lines.append("")
            lines.append(f"Found {len(diagnostics)} error(s).")

        return "\n".join(lines)


class JSONFormatter(Formatter):
    """JSON output formatter compatible with Ruff."""

    def format(self, diagnostics: List[Diagnostic]) -> str:
        """Format diagnostics as JSON."""
        output = [diag.to_dict() for diag in diagnostics]
        return json.dumps(output, indent=2)


class SARIFFormatter(Formatter):
    """SARIF format output for integration with IDEs and CI/CD."""

    def format(self, diagnostics: List[Diagnostic]) -> str:
        """Format diagnostics as SARIF."""
        sarif = {
            "version": "2.1.0",
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "ruff-linter-odoo",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/OCA/ruff-linter-odoo",
                        }
                    },
                    "results": [self._to_sarif_result(diag) for diag in diagnostics],
                }
            ],
        }
        return json.dumps(sarif, indent=2)

    def _to_sarif_result(self, diag: Diagnostic) -> dict:
        """Convert a diagnostic to a SARIF result."""
        level_mapping = {
            "error": "error",
            "warning": "warning",
            "info": "note",
            "convention": "note",
            "refactor": "note",
        }

        return {
            "ruleId": diag.code,
            "level": level_mapping.get(diag.level.value, "warning"),
            "message": {"text": diag.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": diag.filename},
                        "region": {
                            "startLine": diag.line,
                            "startColumn": diag.column,
                            "endLine": diag.end_line or diag.line,
                            "endColumn": diag.end_column or diag.column,
                        },
                    }
                }
            ],
        }


class GitHubFormatter(Formatter):
    """GitHub Actions annotation format."""

    def format(self, diagnostics: List[Diagnostic]) -> str:
        """Format diagnostics as GitHub Actions annotations."""
        lines = []
        for diag in diagnostics:
            level = "error" if diag.level.value == "error" else "warning"
            lines.append(
                f"::{level} file={diag.filename},line={diag.line},col={diag.column},title={diag.code}::{diag.message}"
            )
        return "\n".join(lines)


def get_formatter(format_name: str) -> Formatter:
    """Get a formatter by name."""
    formatters = {
        "text": TextFormatter,
        "json": JSONFormatter,
        "sarif": SARIFFormatter,
        "github": GitHubFormatter,
    }

    formatter_class = formatters.get(format_name.lower())
    if formatter_class is None:
        raise ValueError(f"Unknown format: {format_name}. Available formats: {', '.join(formatters.keys())}")

    return formatter_class()
