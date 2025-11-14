"""Core linter engine for ruff-linter-odoo."""

import ast
from pathlib import Path
from typing import List, Optional

from .config import Config
from .diagnostic import Diagnostic
from .visitor import get_all_checkers


class Linter:
    """Main linter class that orchestrates the linting process."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize the linter with optional configuration."""
        self.config = config or Config()
        self.diagnostics: List[Diagnostic] = []

    def lint_file(self, filepath: Path) -> List[Diagnostic]:
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

        return file_diagnostics

    def lint_directory(self, directory: Path, recursive: bool = True) -> List[Diagnostic]:
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

    def lint_path(self, path: Path) -> List[Diagnostic]:
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
