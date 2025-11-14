"""Odoo-specific linting checks."""

import ast
import re
from typing import Any, Dict, Optional

from ..diagnostic import DiagnosticLevel
from ..visitor import BaseChecker


class PrintChecker(BaseChecker):
    """Check for print statements (should use logger instead)."""

    def visit_Call(self, node: ast.Call):
        """Check for print() calls."""
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            self.add_diagnostic(
                "OCA001",
                "Print used. Use `logger` instead.",
                node,
                DiagnosticLevel.WARNING,
            )
        self.generic_visit(node)


class CommitChecker(BaseChecker):
    """Check for direct cr.commit() usage."""

    def visit_Call(self, node: ast.Call):
        """Check for cr.commit() calls."""
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("cr", "cursor", "_cr")
        ):
            self.add_diagnostic(
                "OCA002",
                "Use of cr.commit() directly - "
                "More info https://github.com/OCA/odoo-community.org/blob/master/website/Contribution/CONTRIBUTING.rst#never-commit-the-transaction",
                node,
                DiagnosticLevel.ERROR,
            )
        self.generic_visit(node)


class SQLInjectionChecker(BaseChecker):
    """Check for potential SQL injection vulnerabilities."""

    def visit_Call(self, node: ast.Call):
        """Check for execute() calls with string formatting."""
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("cr", "cursor", "_cr")
        ):
            # Check if first argument uses string formatting
            if node.args:
                first_arg = node.args[0]
                if self._has_string_formatting(first_arg):
                    self.add_diagnostic(
                        "OCA003",
                        "SQL injection risk. Use parameters if you can. - "
                        "More info https://github.com/OCA/odoo-community.org/blob/master/website/Contribution/CONTRIBUTING.rst#no-sql-injection",
                        node,
                        DiagnosticLevel.ERROR,
                    )
        self.generic_visit(node)

    def _has_string_formatting(self, node: ast.AST) -> bool:
        """Check if node contains string formatting."""
        if isinstance(node, (ast.BinOp, ast.JoinedStr)):
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
                return True
        return False


class ImportChecker(BaseChecker):
    """Check for Odoo-specific import issues."""

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Check imports."""
        if node.module:
            # Check for odoo.addons relative imports
            if "odoo.addons" in node.module:
                # Try to detect if it's the same module
                parts = node.module.split(".")
                if len(parts) >= 3 and parts[0] == "odoo" and parts[1] == "addons":
                    module_name = parts[2]
                    # Check if we're in the same module
                    if self._is_same_module(module_name):
                        self.add_diagnostic(
                            "OCA004",
                            f'Same Odoo module absolute import. You should use relative import with "." '
                            f'instead of "odoo.addons.{module_name}"',
                            node,
                            DiagnosticLevel.WARNING,
                        )

            # Check for deprecated Warning import
            if node.module == "odoo.exceptions":
                for alias in node.names:
                    if alias.name == "Warning":
                        self.add_diagnostic(
                            "OCA005",
                            "`odoo.exceptions.Warning` is a deprecated alias to `odoo.exceptions.UserError` "
                            "use `from odoo.exceptions import UserError`",
                            node,
                            DiagnosticLevel.REFACTOR,
                        )

        self.generic_visit(node)

    def _is_same_module(self, module_name: str) -> bool:
        """Check if we're in the same Odoo module."""
        # Simple heuristic: check if module name is in the file path
        return module_name in self.filename


class MethodChecker(BaseChecker):
    """Check for Odoo method naming conventions."""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check method definitions."""
        # Check for compute/search/inverse method naming
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)

            if decorator_name == "api.depends":
                # This is likely a compute method
                if not node.name.startswith("_compute_"):
                    self.add_diagnostic(
                        "OCA006",
                        'Name of compute method should start with "_compute_"',
                        node,
                        DiagnosticLevel.CONVENTION,
                    )

        # Check method signatures for common Odoo patterns
        self._check_method_super(node)

        self.generic_visit(node)

    def _get_decorator_name(self, decorator: ast.AST) -> Optional[str]:
        """Extract decorator name."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        if isinstance(decorator, ast.Attribute):
            return f"{self._get_name(decorator.value)}.{decorator.attr}"
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                return f"{self._get_name(decorator.func.value)}.{decorator.func.attr}"
        return None

    def _get_name(self, node: ast.AST) -> str:
        """Get name from node."""
        if isinstance(node, ast.Name):
            return node.id
        return ""

    def _check_method_super(self, node: ast.FunctionDef):
        """Check if method properly calls super()."""
        # Methods that should call super: create, write, copy, unlink
        if node.name in ("create", "write", "copy", "unlink"):
            has_super = False
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    if child.func.id == "super":
                        has_super = True
                        break

            # Only warn if the method has a body (not just pass)
            if not has_super and not self._is_empty_method(node):
                self.add_diagnostic(
                    "OCA007",
                    f'Missing `super` call in "{node.name}" method.',
                    node,
                    DiagnosticLevel.WARNING,
                )

    def _is_empty_method(self, node: ast.FunctionDef) -> bool:
        """Check if method is effectively empty."""
        if len(node.body) == 1:
            if isinstance(node.body[0], ast.Pass):
                return True
            if isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, ast.Constant):
                    return True  # Just a docstring
        return False


class TranslationChecker(BaseChecker):
    """Check for translation-related issues."""

    def visit_Call(self, node: ast.Call):
        """Check translation calls."""
        # Check for _() calls
        if isinstance(node.func, ast.Name) and node.func.id == "_":
            # Check for f-strings in translations (Odoo 14+)
            if node.args and isinstance(node.args[0], ast.JoinedStr):
                self.add_diagnostic(
                    "OCA008",
                    "Use lazy % or .format() or % formatting in odoo._ functions",
                    node,
                    DiagnosticLevel.WARNING,
                )

        self.generic_visit(node)


class ManifestChecker(BaseChecker):
    """Check Odoo manifest files."""

    def visit_Module(self, node: ast.Module):
        """Check the manifest file structure."""
        # Parse the manifest dict
        manifest_dict = self._extract_manifest_dict(node)

        if manifest_dict is None:
            return

        self._check_required_keys(manifest_dict, node)
        self._check_license(manifest_dict, node)
        self._check_version_format(manifest_dict, node)
        self._check_author(manifest_dict, node)
        self._check_development_status(manifest_dict, node)

        self.generic_visit(node)

    def _extract_manifest_dict(self, node: ast.Module) -> Optional[Dict[str, Any]]:
        """Extract the manifest dictionary from the AST."""
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Look for common manifest variable assignments
                        if isinstance(item.value, ast.Dict):
                            return self._dict_to_python(item.value)
            elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Dict):
                # Standalone dict (common in manifest files)
                return self._dict_to_python(item.value)
        return None

    def _dict_to_python(self, node: ast.Dict) -> Dict[str, Any]:
        """Convert AST Dict to Python dict."""
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                continue
            key_name = self._get_constant_value(key)
            if key_name:
                result[key_name] = self._get_constant_value(value)
        return result

    def _get_constant_value(self, node: ast.AST) -> Any:
        """Get constant value from AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.List):
            return [self._get_constant_value(elt) for elt in node.elts]
        if isinstance(node, ast.Dict):
            return self._dict_to_python(node)
        if isinstance(node, ast.Str):  # Python 3.7 compatibility
            return node.s
        return None

    def _check_required_keys(self, manifest: Dict[str, Any], node: ast.AST):
        """Check for required manifest keys."""
        required_keys = ["name", "version", "author", "license"]

        for key in required_keys:
            if key not in manifest:
                self.add_diagnostic(
                    "OCA009",
                    f'Missing required key "{key}" in manifest file',
                    node,
                    DiagnosticLevel.CONVENTION,
                )

    def _check_license(self, manifest: Dict[str, Any], node: ast.AST):
        """Check if license is allowed."""
        license_value = manifest.get("license")
        if license_value and license_value not in self.config.license_allowed:
            self.add_diagnostic(
                "OCA010",
                f'License "{license_value}" not allowed in manifest file.',
                node,
                DiagnosticLevel.CONVENTION,
            )

    def _check_version_format(self, manifest: Dict[str, Any], node: ast.AST):
        """Check version format."""
        version = manifest.get("version")
        if version:
            # Odoo version format: X.0.Y.Z.W
            pattern = (
                r"^(4\.2|5\.0|6\.0|6\.1|7\.0|8\.0|9\.0|10\.0|11\.0|12\.0|13\.0|14\.0|"
                r"15\.0|16\.0|17\.0|18\.0|19\.0)\.\d+\.\d+\.\d+$"
            )
            if not re.match(pattern, str(version)):
                self.add_diagnostic(
                    "OCA011",
                    f'Wrong Version Format "{version}" in manifest file. Regex to match: "{pattern}"',
                    node,
                    DiagnosticLevel.CONVENTION,
                )

    def _check_author(self, manifest: Dict[str, Any], node: ast.AST):
        """Check author field."""
        author = manifest.get("author")

        # Check if author is a string
        if author and not isinstance(author, str):
            self.add_diagnostic(
                "OCA012",
                "The author key in the manifest file must be a string (with comma separated values)",
                node,
                DiagnosticLevel.ERROR,
            )
            return

        # Check if required authors are present
        if author:
            for required_author in self.config.manifest_required_authors:
                if required_author not in author:
                    authors_list = ", ".join(self.config.manifest_required_authors)
                    self.add_diagnostic(
                        "OCA013",
                        f"One of the following authors must be present in manifest: {authors_list}",
                        node,
                        DiagnosticLevel.CONVENTION,
                    )
                    break

    def _check_development_status(self, manifest: Dict[str, Any], node: ast.AST):
        """Check development_status field."""
        dev_status = manifest.get("development_status")
        if dev_status and dev_status not in self.config.development_status_allowed:
            allowed_statuses = ", ".join(self.config.development_status_allowed)
            self.add_diagnostic(
                "OCA014",
                f'Manifest key development_status "{dev_status}" not allowed. Use one of: {allowed_statuses}.',
                node,
                DiagnosticLevel.CONVENTION,
            )
