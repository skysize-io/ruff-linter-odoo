"""AST visitor base classes and checker registry."""

import ast
from typing import List

from .config import Config
from .diagnostic import Diagnostic, DiagnosticLevel


class BaseChecker(ast.NodeVisitor):
    """Base class for all AST-based checkers."""

    def __init__(self, config: Config, filename: str, source_code: str):
        """Initialize the checker."""
        self.config = config
        self.filename = filename
        self.source_code = source_code
        self.diagnostics: List[Diagnostic] = []
        self.source_lines = source_code.splitlines()

    def add_diagnostic(
        self,
        code: str,
        message: str,
        node: ast.AST,
        level: DiagnosticLevel = DiagnosticLevel.WARNING,
    ):
        """Add a diagnostic for a node."""
        if not self.config.is_check_enabled(code):
            return

        diagnostic = Diagnostic(
            code=code,
            message=message,
            filename=self.filename,
            line=node.lineno if hasattr(node, "lineno") else 1,
            column=node.col_offset if hasattr(node, "col_offset") else 0,
            level=level,
            end_line=getattr(node, "end_lineno", None),
            end_column=getattr(node, "end_col_offset", None),
        )
        self.diagnostics.append(diagnostic)


def get_all_checkers(config: Config, filename: str, source_code: str) -> List[BaseChecker]:
    """Get all registered checkers."""
    from .checkers.odoo_checkers import (
        CommitChecker,
        ImportChecker,
        ManifestChecker,
        MethodChecker,
        PrintChecker,
        SQLInjectionChecker,
        TranslationChecker,
    )

    checker_classes = [
        PrintChecker,
        CommitChecker,
        SQLInjectionChecker,
        ImportChecker,
        MethodChecker,
        TranslationChecker,
    ]

    # Add manifest checker if this is a manifest file
    if filename.endswith(("__manifest__.py", "__openerp__.py")):
        checker_classes.append(ManifestChecker)

    return [checker_class(config, filename, source_code) for checker_class in checker_classes]
