"""Core linter engine for ruff-linter-odoo."""

import ast
import io
import re
import tokenize
from pathlib import Path
from typing import Optional

from .config import Config
from .diagnostic import Diagnostic
from .visitor import get_all_checkers

#: Ruff-style inline suppression: `# noqa` or `# noqa: OCA001, OCA002`
NOQA_RE = re.compile(r"#\s*noqa(?::\s*(?P<codes>[A-Z][A-Z0-9]*(?:[,\s]+[A-Z][A-Z0-9]*)*))?", re.IGNORECASE)


class Linter:
    """Main linter class that orchestrates the linting process."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize the linter with optional configuration."""
        self.config = config or Config()
        self.diagnostics: list[Diagnostic] = []

    def lint_file(self, filepath: Path) -> list[Diagnostic]:
        """Lint a single Python file."""
        try:
            with open(filepath, encoding="utf-8") as f:
                source_code = f.read()
        except (OSError, UnicodeDecodeError):
            return []

        try:
            tree = ast.parse(source_code, filename=str(filepath))
        except SyntaxError:
            # Skip files with syntax errors - they should be caught by other tools
            return []

        file_diagnostics = []
        checkers = get_all_checkers(self.config, str(filepath), source_code)

        for checker in checkers:
            checker.visit(tree)
            file_diagnostics.extend(checker.diagnostics)

        return self._filter_noqa(file_diagnostics, source_code)

    def _filter_noqa(self, diagnostics: list[Diagnostic], source_code: str) -> list[Diagnostic]:
        """Drop diagnostics suppressed by a `# noqa` comment on their line."""
        if "noqa" not in source_code:
            return diagnostics
        noqa_lines = self._collect_noqa_lines(source_code)
        if not noqa_lines:
            return diagnostics
        kept = []
        for diag in diagnostics:
            codes = noqa_lines.get(diag.line)
            if codes is None or (codes and diag.code not in codes):
                kept.append(diag)
        return kept

    @staticmethod
    def _collect_noqa_lines(source_code: str) -> dict[int, set[str]]:
        """Map line numbers to suppressed codes (empty set = suppress all)."""
        noqa_lines: dict[int, set[str]] = {}
        try:
            tokens = tokenize.generate_tokens(io.StringIO(source_code).readline)
            for token in tokens:
                if token.type != tokenize.COMMENT:
                    continue
                match = NOQA_RE.search(token.string)
                if not match:
                    continue
                codes = match.group("codes")
                if codes:
                    noqa_lines[token.start[0]] = {code.strip().upper() for code in re.split(r"[,\s]+", codes)}
                else:
                    # Bare `# noqa` suppresses everything on the line
                    noqa_lines[token.start[0]] = set()
        except tokenize.TokenizeError:
            pass
        return noqa_lines

    def lint_directory(self, directory: Path, recursive: bool = True) -> list[Diagnostic]:
        """Lint all Python files in a directory."""
        all_diagnostics = []

        pattern = "**/*.py" if recursive else "*.py"

        for filepath in directory.glob(pattern):
            # Check if file should be excluded
            if self._should_exclude(filepath):
                continue

            diagnostics = self.lint_file(filepath)
            all_diagnostics.extend(diagnostics)

        return all_diagnostics

    def lint_path(self, path: Path) -> list[Diagnostic]:
        """Lint a file or directory."""
        if path.is_file():
            return self.lint_file(path)
        if path.is_dir():
            return self.lint_directory(path)
        return []

    def _should_exclude(self, filepath: Path) -> bool:
        """Check if a file should be excluded based on configuration."""
        path_str = str(filepath)
        return any(pattern in path_str for pattern in self.config.exclude)
