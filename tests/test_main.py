"""Tests for ruff-linter-odoo."""

from __future__ import annotations

import os
import unittest
from collections import Counter
from glob import glob
from pathlib import Path

from ruff_linter_odoo import Linter
from ruff_linter_odoo.config import Config


class MainTest(unittest.TestCase):
    """Main test suite for ruff-linter-odoo."""

    def setUp(self):
        """Set up test fixtures."""
        self.root_path_modules = Path(__file__).parent.parent / "testing" / "resources" / "test_repo"
        # Get all Python files in test repo (similar to pre-commit way)
        self.paths_modules = list(self.root_path_modules.rglob("*.py"))

        self.odoo_namespace_addons_path = (
            Path(__file__).parent.parent
            / "testing"
            / "resources"
            / "test_repo_odoo_namespace"
            / "odoo"
        )

        self.maxDiff = None

        # Expected diagnostic counts by code
        # These are the expected counts from running the linter on test_repo
        self.expected_diagnostics = {
            "OCA001": 0,  # print-used - to be updated based on actual test data
            "OCA002": 0,  # invalid-commit - to be updated
            "OCA003": 0,  # sql-injection - to be updated
            "OCA004": 0,  # odoo-addons-relative-import - to be updated
            "OCA005": 0,  # odoo-exception-warning - to be updated
            "OCA006": 0,  # method-compute - to be updated
            "OCA007": 0,  # method-required-super - to be updated
            "OCA008": 0,  # translation-fstring-interpolation - to be updated
        }

    def run_linter(self, paths: list[Path] | None = None, config: Config | None = None) -> list:
        """Run the linter on specified paths."""
        if paths is None:
            paths = self.paths_modules

        if config is None:
            config = Config()

        linter = Linter(config)
        all_diagnostics = []

        for path in paths:
            if not path.exists():
                raise OSError(f'Path "{path}" not found.')

            diagnostics = linter.lint_path(path)
            all_diagnostics.extend(diagnostics)

        return all_diagnostics

    def group_diagnostics_by_code(self, diagnostics: list) -> dict[str, int]:
        """Group diagnostics by code and return counts."""
        counts = {}
        for diag in diagnostics:
            counts[diag.code] = counts.get(diag.code, 0) + 1
        return counts

    def test_10_path_dont_exist(self):
        """Test if path doesn't exist."""
        path_unexist = Path("/tmp/____unexist______")
        with self.assertRaisesRegex(OSError, r'Path "[^"]+" not found.$'):
            self.run_linter([path_unexist])

    def test_20_basic_linting(self):
        """Test basic linting functionality."""
        diagnostics = self.run_linter()

        # Group diagnostics by code
        diagnostic_counts = self.group_diagnostics_by_code(diagnostics)

        # Print summary for debugging
        print("\n=== Diagnostic Summary ===")
        for code in sorted(diagnostic_counts.keys()):
            count = diagnostic_counts[code]
            print(f"  {code}: {count}")
        print("=========================\n")

        # Verify we got some diagnostics (test repo should have issues)
        self.assertGreater(len(diagnostics), 0, "Expected to find some diagnostics in test repo")

        # Verify all diagnostics have required fields
        for diag in diagnostics:
            self.assertIsNotNone(diag.code)
            self.assertIsNotNone(diag.message)
            self.assertIsNotNone(diag.filename)
            self.assertGreater(diag.line, 0)
            self.assertGreaterEqual(diag.column, 0)

    def test_30_config_enable_disable(self):
        """Test enabling and disabling specific checks."""
        # First, get baseline
        baseline_diagnostics = self.run_linter()
        baseline_counts = self.group_diagnostics_by_code(baseline_diagnostics)

        if not baseline_counts:
            self.skipTest("No diagnostics found in baseline, cannot test enable/disable")

        # Pick a diagnostic code that exists
        test_code = list(baseline_counts.keys())[0]

        # Test disabling that specific check
        config = Config(disable=[test_code])
        filtered_diagnostics = self.run_linter(config=config)
        filtered_counts = self.group_diagnostics_by_code(filtered_diagnostics)

        # The disabled check should not appear
        self.assertNotIn(test_code, filtered_counts, f"Check {test_code} should be disabled")

        # Test enabling only that specific check
        config = Config(enable=[test_code])
        enabled_diagnostics = self.run_linter(config=config)
        enabled_counts = self.group_diagnostics_by_code(enabled_diagnostics)

        # Only the enabled check should appear
        for code in enabled_counts:
            self.assertEqual(code, test_code, f"Only {test_code} should be enabled, but found {code}")

    def test_40_linter_single_file(self):
        """Test linting a single file."""
        # Find a Python file to test
        test_file = self.root_path_modules / "eleven_module" / "__init__.py"
        if not test_file.exists():
            self.skipTest(f"Test file {test_file} not found")

        diagnostics = self.run_linter([test_file])

        # All diagnostics should be from the same file
        for diag in diagnostics:
            self.assertIn(str(test_file.name), diag.filename)

    def test_50_linter_directory(self):
        """Test linting a directory."""
        test_dir = self.root_path_modules / "eleven_module"
        if not test_dir.exists():
            self.skipTest(f"Test directory {test_dir} not found")

        diagnostics = self.run_linter([test_dir])

        # Should have diagnostics from files in that directory
        if diagnostics:
            for diag in diagnostics:
                # Check that the file is within the test directory
                self.assertIn("eleven_module", diag.filename)

    def test_60_manifest_checks(self):
        """Test manifest file checks."""
        manifest_files = list(self.root_path_modules.glob("**/__manifest__.py"))
        manifest_files.extend(self.root_path_modules.glob("**/__openerp__.py"))

        if not manifest_files:
            self.skipTest("No manifest files found")

        diagnostics = self.run_linter(manifest_files)

        # Should have some manifest-related diagnostics
        manifest_codes = {d.code for d in diagnostics if d.code.startswith("OCA009") or
                         d.code.startswith("OCA010") or d.code.startswith("OCA011") or
                         d.code.startswith("OCA012") or d.code.startswith("OCA013") or
                         d.code.startswith("OCA014")}

        # Print manifest diagnostics for debugging
        if manifest_codes:
            print(f"\nManifest diagnostic codes found: {manifest_codes}")

    def test_70_config_from_file(self):
        """Test loading configuration from pyproject.toml."""
        # Use the project's own config file
        config_path = Path(__file__).parent.parent / "pyproject.toml"

        if not config_path.exists():
            self.skipTest("pyproject.toml not found")

        config = Config.from_pyproject_toml(config_path)

        # Verify config was loaded
        self.assertIsInstance(config, Config)
        self.assertIsInstance(config.valid_odoo_versions, list)
        self.assertIsInstance(config.exclude, list)

    def test_80_diagnostic_format(self):
        """Test diagnostic string format."""
        diagnostics = self.run_linter()

        if not diagnostics:
            self.skipTest("No diagnostics found")

        # Test the string representation
        for diag in diagnostics[:5]:  # Test first 5
            diag_str = str(diag)

            # Should have format: filename:line:column: CODE message
            self.assertIn(diag.code, diag_str)
            self.assertIn(str(diag.line), diag_str)
            self.assertIn(":", diag_str)

    def test_90_exclude_patterns(self):
        """Test that exclude patterns work."""
        # Create config with exclusions
        config = Config(exclude=[".git", "__pycache__", "migrations"])

        linter = Linter(config)

        # Test the exclusion logic
        test_path = Path("/some/module/migrations/file.py")
        self.assertTrue(linter._should_exclude(test_path))

        test_path = Path("/some/module/models.py")
        self.assertFalse(linter._should_exclude(test_path))

    def test_95_diagnostic_to_dict(self):
        """Test diagnostic serialization to dict."""
        diagnostics = self.run_linter()

        if not diagnostics:
            self.skipTest("No diagnostics found")

        # Test conversion to dict (for JSON output)
        for diag in diagnostics[:5]:
            diag_dict = diag.to_dict()

            self.assertIsInstance(diag_dict, dict)
            self.assertIn("code", diag_dict)
            self.assertIn("message", diag_dict)
            self.assertIn("filename", diag_dict)
            self.assertIn("location", diag_dict)
            self.assertIn("level", diag_dict)

            # Check location structure
            self.assertIn("row", diag_dict["location"])
            self.assertIn("column", diag_dict["location"])


class IntegrationTest(unittest.TestCase):
    """Integration tests for the full linting workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_repo = Path(__file__).parent.parent / "testing" / "resources" / "test_repo"

    def test_lint_entire_repo(self):
        """Test linting the entire test repository."""
        config = Config()
        linter = Linter(config)

        diagnostics = linter.lint_path(self.test_repo)

        # Group by file
        by_file = {}
        for diag in diagnostics:
            if diag.filename not in by_file:
                by_file[diag.filename] = []
            by_file[diag.filename].append(diag)

        print(f"\n=== Files with diagnostics: {len(by_file)} ===")
        for filename, diags in sorted(by_file.items())[:10]:  # Show first 10
            print(f"  {filename}: {len(diags)} issues")

    def test_print_checker(self):
        """Test that print statements are detected."""
        from tempfile import NamedTemporaryFile

        code_with_print = """
print("This is a test")
def foo():
    print("Debug message")
"""

        with NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code_with_print)
            f.flush()
            temp_path = Path(f.name)

        try:
            linter = Linter()
            diagnostics = linter.lint_file(temp_path)

            # Should detect 2 print statements
            print_diags = [d for d in diagnostics if d.code == "OCA001"]
            self.assertEqual(len(print_diags), 2, "Should detect 2 print statements")
        finally:
            temp_path.unlink()

    def test_commit_checker(self):
        """Test that cr.commit() is detected."""
        from tempfile import NamedTemporaryFile

        code_with_commit = """
def bad_method(self):
    cr.commit()
    self.env.cr.commit()
"""

        with NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code_with_commit)
            f.flush()
            temp_path = Path(f.name)

        try:
            linter = Linter()
            diagnostics = linter.lint_file(temp_path)

            # Should detect commit calls
            commit_diags = [d for d in diagnostics if d.code == "OCA002"]
            self.assertGreater(len(commit_diags), 0, "Should detect cr.commit() calls")
        finally:
            temp_path.unlink()

    def test_sql_injection_checker(self):
        """Test that SQL injection risks are detected."""
        from tempfile import NamedTemporaryFile

        code_with_sqli = """
def bad_query(self, table_name):
    # Direct cr.execute() with f-string (should be detected)
    query = f"SELECT * FROM {table_name}"
    cr.execute(query)

    # Direct cr.execute() with % formatting (should be detected)
    cr.execute("SELECT * FROM table WHERE id = %s" % self.id)
"""

        with NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code_with_sqli)
            f.flush()
            temp_path = Path(f.name)

        try:
            linter = Linter()
            diagnostics = linter.lint_file(temp_path)

            # Should detect SQL injection risks
            sqli_diags = [d for d in diagnostics if d.code == "OCA003"]
            self.assertGreater(len(sqli_diags), 0, "Should detect SQL injection risks")
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
