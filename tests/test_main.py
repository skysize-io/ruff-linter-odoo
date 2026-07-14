"""Tests for ruff-linter-odoo."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ruff_linter_odoo import Linter
from ruff_linter_odoo.config import Config

# Expected diagnostic counts from linting testing/resources/test_repo.
#
# Where the count differs from upstream pylint-odoo's reference run
# (commit 0a98430, tests/test_main.py EXPECTED_ERRORS) the reason is noted.
# The known, intentional divergences are:
#   * OCA008/027/028/029/030/031/032 also cover `_lt()` calls. Upstream skips
#     `_lt` because its checks are derived from pylint's logging checker,
#     which only recognizes `_` — a lazily-translated string has the same
#     bugs, so we check it too.
#   * OCA009 requires name/version/author/license by default (upstream only
#     requires license). Configurable via `manifest-required-keys`.
#   * OCA013 requires no particular author by default (upstream requires the
#     OCA). Opt-in via `manifest-required-authors`.
EXPECTED_DIAGNOSTICS = {
    "OCA001": 1,  # print-used (upstream W8116: 1)
    "OCA002": 4,  # invalid-commit (upstream E8102: 4)
    "OCA003": 21,  # sql-injection (upstream E8103: 21)
    "OCA004": 4,  # odoo-addons-relative-import (upstream W8150: 4)
    "OCA005": 4,  # odoo-exception-warning (upstream R8101: 4)
    "OCA006": 2,  # method-compute (upstream C8108: 2)
    "OCA007": 8,  # method-required-super (upstream W8106: 8)
    "OCA008": 63,  # translation-not-lazy (upstream W8301: 42 — we also check _lt)
    "OCA009": 7,  # manifest-required-key (upstream C8102: 1 — we require 4 keys by default)
    "OCA010": 1,  # license-allowed (upstream C8105: 1)
    "OCA011": 3,  # manifest-version-format (upstream C8106: 3)
    "OCA012": 1,  # manifest-author-string (upstream E8101: 1)
    "OCA013": 0,  # manifest-required-author (upstream C8101: 1 — no required author by default)
    "OCA014": 1,  # development-status-allowed (upstream C8111: 1)
    "OCA015": 1,  # manifest-deprecated-key (upstream C8103: 1)
    "OCA016": 1,  # manifest-maintainers-list (upstream E8104: 1)
    "OCA017": 1,  # manifest-data-duplicated (upstream W8125: 1)
    "OCA018": 3,  # manifest-behind-migrations (upstream E8145: 3)
    "OCA019": 3,  # manifest-external-assets (upstream W8162: 3)
    "OCA020": 1,  # missing-readme (upstream C8112: 1)
    "OCA021": 2,  # website-manifest-key-not-valid-uri (upstream W8114: 2)
    "OCA022": 4,  # resource-not-exist (upstream F8101: 4)
    "OCA023": 16,  # translation-required (upstream C8107: 16)
    "OCA024": 33,  # translation-contains-variable (upstream W8115: 33)
    "OCA025": 30,  # translation-positional-used (upstream W8120: 30)
    "OCA026": 3,  # translation-field (upstream W8103: 3)
    "OCA027": 33,  # translation-format-interpolation (upstream W8302: 22 — we also check _lt)
    "OCA028": 4,  # translation-fstring-interpolation (upstream W8303: 3 — we also check _lt)
    "OCA029": 3,  # translation-format-truncated (upstream E8301: 2 — we also check _lt)
    "OCA030": 3,  # translation-too-few-args (upstream E8306: 2 — we also check _lt)
    "OCA031": 3,  # translation-too-many-args (upstream E8305: 2 — we also check _lt)
    "OCA032": 3,  # translation-unsupported-format (upstream E8300: 2 — we also check _lt)
    "OCA033": 112,  # prefer-env-translation (upstream W8161: 112)
    "OCA034": 2,  # method-inverse (upstream C8110: 2)
    "OCA035": 2,  # method-search (upstream C8109: 2)
}


class LintHelperMixin:
    """Helpers for linting inline source snippets."""

    def lint_source(self, source: str, filename: str = "module_file.py", config: Config | None = None) -> list:
        """Lint a source snippet written to a temporary file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
            return Linter(config or Config()).lint_file(path)

    def lint_manifest(self, manifest_source: str, config: Config | None = None, extra_files: dict | None = None):
        """Lint a __manifest__.py inside a temporary module directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            module_dir = Path(tmpdir) / "my_module"
            module_dir.mkdir()
            for name, content in (extra_files or {}).items():
                file_path = module_dir / name
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
            manifest = module_dir / "__manifest__.py"
            manifest.write_text(manifest_source, encoding="utf-8")
            return Linter(config or Config()).lint_file(manifest)

    def codes(self, diagnostics: list) -> list:
        return [d.code for d in diagnostics]

    def assert_code(self, source: str, code: str, **kwargs):
        diagnostics = self.lint_source(source, **kwargs)
        self.assertIn(code, self.codes(diagnostics), f"Expected {code} in:\n{source}")

    def assert_no_code(self, source: str, code: str, **kwargs):
        diagnostics = self.lint_source(source, **kwargs)
        self.assertNotIn(code, self.codes(diagnostics), f"Did not expect {code} in:\n{source}")


class MainTest(LintHelperMixin, unittest.TestCase):
    """Main test suite for ruff-linter-odoo."""

    def setUp(self):
        """Set up test fixtures."""
        self.root_path_modules = Path(__file__).parent.parent / "testing" / "resources" / "test_repo"
        # Get all Python files in test repo (similar to pre-commit way)
        self.paths_modules = sorted(self.root_path_modules.rglob("*.py"))
        self.maxDiff = None

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

    def test_20_expected_diagnostics(self):
        """Pin the exact per-rule diagnostic counts for the test repo."""
        diagnostics = self.run_linter()
        diagnostic_counts = self.group_diagnostics_by_code(diagnostics)
        # Zero-count rules do not appear in the Counter
        expected = {code: count for code, count in EXPECTED_DIAGNOSTICS.items() if count}
        self.assertDictEqual(diagnostic_counts, expected)

        # Verify all diagnostics have required fields
        for diag in diagnostics:
            self.assertIsNotNone(diag.code)
            self.assertIsNotNone(diag.message)
            self.assertIsNotNone(diag.filename)
            self.assertGreater(diag.line, 0)
            self.assertGreaterEqual(diag.column, 0)

    def test_30_config_enable_disable(self):
        """Test enabling and disabling specific checks."""
        baseline_counts = self.group_diagnostics_by_code(self.run_linter())
        test_code = sorted(baseline_counts.keys())[0]

        # Test disabling that specific check
        config = Config(disable=[test_code])
        filtered_counts = self.group_diagnostics_by_code(self.run_linter(config=config))
        self.assertNotIn(test_code, filtered_counts, f"Check {test_code} should be disabled")

        # Test enabling only that specific check
        config = Config(enable=[test_code])
        enabled_counts = self.group_diagnostics_by_code(self.run_linter(config=config))
        self.assertEqual(list(enabled_counts.keys()), [test_code])
        self.assertEqual(enabled_counts[test_code], baseline_counts[test_code])

    def test_40_linter_single_file(self):
        """Test linting a single file."""
        test_file = self.root_path_modules / "eleven_module" / "__init__.py"
        self.assertTrue(test_file.exists())

        diagnostics = self.run_linter([test_file])

        # All diagnostics should be from the same file
        for diag in diagnostics:
            self.assertIn(str(test_file.name), diag.filename)

    def test_50_linter_directory(self):
        """Test linting a directory."""
        test_dir = self.root_path_modules / "eleven_module"
        self.assertTrue(test_dir.exists())

        diagnostics = self.run_linter([test_dir])
        for diag in diagnostics:
            self.assertIn("eleven_module", diag.filename)

    def test_70_config_from_file(self):
        """Test loading configuration from pyproject.toml."""
        config_path = Path(__file__).parent.parent / "pyproject.toml"
        self.assertTrue(config_path.exists())

        config = Config.from_pyproject_toml(config_path)

        self.assertIsInstance(config, Config)
        self.assertIsInstance(config.valid_odoo_versions, list)
        self.assertIsInstance(config.exclude, list)

    def test_80_diagnostic_format(self):
        """Test diagnostic string format."""
        diagnostics = self.run_linter()
        self.assertTrue(diagnostics)

        # Should have format: filename:line:column: CODE message
        for diag in diagnostics[:5]:
            diag_str = str(diag)
            self.assertIn(diag.code, diag_str)
            self.assertIn(str(diag.line), diag_str)
            self.assertIn(":", diag_str)

    def test_90_exclude_patterns(self):
        """Test that exclude patterns work."""
        config = Config(exclude=[".git", "__pycache__", "migrations"])
        linter = Linter(config)

        self.assertTrue(linter._should_exclude(Path("/some/module/migrations/file.py")))
        self.assertFalse(linter._should_exclude(Path("/some/module/models.py")))

    def test_95_diagnostic_to_dict(self):
        """Test diagnostic serialization to dict."""
        diagnostics = self.run_linter()
        self.assertTrue(diagnostics)

        for diag in diagnostics[:5]:
            diag_dict = diag.to_dict()

            self.assertIsInstance(diag_dict, dict)
            self.assertIn("code", diag_dict)
            self.assertIn("message", diag_dict)
            self.assertIn("filename", diag_dict)
            self.assertIn("location", diag_dict)
            self.assertIn("level", diag_dict)
            self.assertIn("row", diag_dict["location"])
            self.assertIn("column", diag_dict["location"])


class NoqaTest(LintHelperMixin, unittest.TestCase):
    """Tests for ruff-style `# noqa` inline suppression."""

    def test_bare_noqa_suppresses_all(self):
        self.assert_no_code('print("x")  # noqa\n', "OCA001")

    def test_noqa_with_matching_code(self):
        self.assert_no_code('print("x")  # noqa: OCA001\n', "OCA001")

    def test_noqa_with_multiple_codes(self):
        self.assert_no_code('print("x")  # noqa: OCA002, OCA001\n', "OCA001")

    def test_noqa_with_other_code_does_not_suppress(self):
        self.assert_code('print("x")  # noqa: OCA002\n', "OCA001")

    def test_noqa_only_affects_its_line(self):
        source = 'print("a")  # noqa\nprint("b")\n'
        diagnostics = self.lint_source(source)
        self.assertEqual(self.codes(diagnostics), ["OCA001"])
        self.assertEqual(diagnostics[0].line, 2)

    def test_noqa_in_string_literal_is_ignored(self):
        self.assert_code('print("this mentions # noqa in a string")\n', "OCA001")


class PythonRulesTest(LintHelperMixin, unittest.TestCase):
    """One focused positive + negative test per Python-code rule."""

    def test_oca001_print_used(self):
        self.assert_code('print("hello")\n', "OCA001")
        self.assert_no_code('_logger.info("hello")\n', "OCA001")

    def test_oca002_invalid_commit(self):
        for cursor in ("cr", "self._cr", "self.cr", "self.env.cr"):
            self.assert_code(f"def method(self):\n    {cursor}.commit()\n", "OCA002")
        self.assert_no_code("def method(self):\n    self.env.cr2.commit()\n", "OCA002")
        self.assert_no_code("def method(self):\n    self.env.cr.commit2()\n", "OCA002")

    def test_oca003_sql_injection(self):
        self.assert_code(
            "def q(self, ids):\n    self._cr.execute('SELECT * FROM t WHERE id IN %s' % (tuple(ids),))\n",
            "OCA003",
        )
        self.assert_code(
            "def q(self, ids):\n    self.cr.execute('SELECT * FROM t WHERE id IN {}'.format(ids))\n",
            "OCA003",
        )
        self.assert_code(
            "def q(self, table):\n    self.cr.execute(f'SELECT * FROM {table}')\n",
            "OCA003",
        )
        self.assert_code(
            "def q(self, ids):\n    var = 'SELECT * FROM t WHERE id IN %s'\n    self._cr.execute(var % ids)\n",
            "OCA003",
        )
        # Parameterized query: fine
        self.assert_no_code(
            "def q(self, ids):\n    self._cr.execute('SELECT * FROM t WHERE id IN %s', (tuple(ids),))\n",
            "OCA003",
        )
        # Private attribute (self._table): fine
        self.assert_no_code(
            "def q(self, ids):\n    self._cr.execute('DELETE FROM %s WHERE id IN %%s' % self._table, (ids,))\n",
            "OCA003",
        )
        # psycopg2.sql composition: fine
        self.assert_no_code(
            "from psycopg2 import sql\n"
            "def q(self):\n"
            "    self._cr.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(self._table)))\n",
            "OCA003",
        )

    def test_oca004_odoo_addons_relative_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            module_dir = Path(tmpdir) / "my_module"
            module_dir.mkdir()
            (module_dir / "__manifest__.py").write_text("{'name': 'x'}\n", encoding="utf-8")
            model = module_dir / "models.py"

            model.write_text("from odoo.addons.my_module import helpers\n", encoding="utf-8")
            self.assertIn("OCA004", self.codes(Linter().lint_file(model)))

            model.write_text("from odoo.addons import my_module\n", encoding="utf-8")
            self.assertIn("OCA004", self.codes(Linter().lint_file(model)))

            model.write_text("import odoo.addons.my_module.helpers\n", encoding="utf-8")
            self.assertIn("OCA004", self.codes(Linter().lint_file(model)))

            # Importing another module is fine
            model.write_text("from odoo.addons.other_module import helpers\n", encoding="utf-8")
            self.assertNotIn("OCA004", self.codes(Linter().lint_file(model)))

    def test_oca005_odoo_exception_warning(self):
        self.assert_code("from odoo.exceptions import Warning\n", "OCA005")
        self.assert_no_code("from odoo.exceptions import UserError\n", "OCA005")

    def test_oca006_method_compute(self):
        self.assert_code("name = fields.Char(compute='calc_name')\n", "OCA006")
        self.assert_no_code("name = fields.Char(compute='_compute_name')\n", "OCA006")

    def test_oca034_method_inverse(self):
        self.assert_code("name = fields.Char(inverse='set_name')\n", "OCA034")
        self.assert_no_code("name = fields.Char(inverse='_inverse_name')\n", "OCA034")

    def test_oca035_method_search(self):
        self.assert_code("name = fields.Char(search='find_name')\n", "OCA035")
        self.assert_no_code("name = fields.Char(search='_search_name')\n", "OCA035")

    def test_oca007_method_required_super(self):
        self.assert_code(
            "class MyModel(models.Model):\n    def create(self, vals):\n        return vals\n",
            "OCA007",
        )
        self.assert_no_code(
            "class MyModel(models.Model):\n    def create(self, vals):\n        return super().create(vals)\n",
            "OCA007",
        )
        # Plain functions (not methods) are fine
        self.assert_no_code("def create(vals):\n    return vals\n", "OCA007")

    def test_oca008_translation_not_lazy(self):
        self.assert_code("def m(self, name):\n    msg = _('Hello %s' % name)\n", "OCA008")
        self.assert_code("def m(self, name):\n    msg = _('Hello %s') % name\n", "OCA008")
        self.assert_code("def m(self, name):\n    msg = _lt('Hello %s') % name\n", "OCA008")
        self.assert_no_code("def m(self, name):\n    msg = _('Hello %s', name)\n", "OCA008")

    def test_oca023_translation_required(self):
        self.assert_code(
            "def m(self):\n    raise UserError('String without translation')\n",
            "OCA023",
        )
        self.assert_code(
            "def m(self):\n    raise UserError(f'missing translation {self.x}')\n",
            "OCA023",
        )
        self.assert_code(
            "def m(self):\n    self.message_post(body='Untranslated body')\n",
            "OCA023",
        )
        self.assert_no_code(
            "def m(self):\n    raise UserError(_('Translated'))\n",
            "OCA023",
        )
        self.assert_no_code(
            "def m(self):\n    self.message_post(body=_('Translated'))\n",
            "OCA023",
        )
        # Non-Odoo exceptions are not required to be translated
        self.assert_no_code(
            "def m(self):\n    raise ZeroDivisionError('Not an Odoo exception')\n",
            "OCA023",
        )

    def test_oca024_translation_contains_variable(self):
        self.assert_code("def m(self, name):\n    msg = _('Hello %s' % name)\n", "OCA024")
        self.assert_code("def m(self, name):\n    msg = _('Hello {}'.format(name))\n", "OCA024")
        self.assert_no_code("def m(self, name):\n    msg = _('Hello %s') % name\n", "OCA024")

    def test_oca025_translation_positional_used(self):
        self.assert_code("msg = _('%s %s')\n", "OCA025")
        self.assert_code("def m(self, a, b):\n    msg = _('%s %s' % (a, b))\n", "OCA025")
        self.assert_no_code("msg = _('%(a)s %(b)s')\n", "OCA025")
        self.assert_no_code("msg = _('%s')\n", "OCA025")

    def test_oca026_translation_field(self):
        self.assert_code("name = fields.Char(string=_('Name'))\n", "OCA026")
        self.assert_no_code("name = fields.Char(string='Name')\n", "OCA026")

    def test_oca027_translation_format_interpolation(self):
        self.assert_code("def m(self, name):\n    msg = _('Hello {}'.format(name))\n", "OCA027")
        self.assert_code("def m(self, name):\n    msg = _('Hello {}').format(name)\n", "OCA027")
        self.assert_no_code("def m(self, name):\n    msg = _('Hello %s', name)\n", "OCA027")

    def test_oca028_translation_fstring_interpolation(self):
        self.assert_code("def m(self, name):\n    msg = _(f'Hello {name}')\n", "OCA028")
        self.assert_no_code("def m(self, name):\n    msg = _('Hello %s', name)\n", "OCA028")

    def test_oca029_translation_format_truncated(self):
        self.assert_code("msg = _('truncated %s%', 'a')\n", "OCA029")
        self.assert_no_code("msg = _('fine %s', 'a')\n", "OCA029")

    def test_oca030_translation_too_few_args(self):
        self.assert_code("msg = _('%s %s', 'a')\n", "OCA030")
        self.assert_no_code("msg = _('%s %s', 'a', 'b')\n", "OCA030")

    def test_oca031_translation_too_many_args(self):
        self.assert_code("msg = _('%s', 'a', 'b')\n", "OCA031")
        self.assert_no_code("msg = _('%s %s', 'a', 'b')\n", "OCA031")

    def test_oca032_translation_unsupported_format(self):
        self.assert_code("msg = _('bad %y placeholder', 'a')\n", "OCA032")
        self.assert_no_code("msg = _('good %s placeholder', 'a')\n", "OCA032")

    def test_oca033_prefer_env_translation(self):
        self.assert_code("def m(self):\n    return _('Hello')\n", "OCA033")
        self.assert_no_code("def m(self):\n    return self.env._('Hello')\n", "OCA033")
        # Only relevant for Odoo >= 18.0
        config = Config(valid_odoo_versions=["16.0"])
        self.assert_no_code("def m(self):\n    return _('Hello')\n", "OCA033", config=config)


class ManifestRulesTest(LintHelperMixin, unittest.TestCase):
    """One focused positive + negative test per manifest rule."""

    GOOD_MANIFEST = "{'name': 'My Module', 'version': '16.0.1.0.0', 'author': 'Skysize', 'license': 'AGPL-3'}\n"

    def test_good_manifest_is_clean(self):
        diagnostics = self.lint_manifest(self.GOOD_MANIFEST, extra_files={"README.rst": "readme"})
        self.assertEqual(self.codes(diagnostics), [])

    def test_oca009_manifest_required_key(self):
        diagnostics = self.lint_manifest("{'name': 'My Module'}\n")
        counts = self.codes(diagnostics).count("OCA009")
        self.assertEqual(counts, 3)  # version, author, license missing
        self.assertNotIn("OCA009", self.codes(self.lint_manifest(self.GOOD_MANIFEST)))

    def test_oca010_license_allowed(self):
        bad = "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'WTFPL'}\n"
        self.assertIn("OCA010", self.codes(self.lint_manifest(bad)))
        self.assertNotIn("OCA010", self.codes(self.lint_manifest(self.GOOD_MANIFEST)))

    def test_oca011_manifest_version_format(self):
        bad = "{'name': 'x', 'version': '1.0', 'author': 'a', 'license': 'AGPL-3'}\n"
        self.assertIn("OCA011", self.codes(self.lint_manifest(bad)))
        self.assertNotIn("OCA011", self.codes(self.lint_manifest(self.GOOD_MANIFEST)))

    def test_oca012_manifest_author_string(self):
        bad = "{'name': 'x', 'version': '16.0.1.0.0', 'author': ['a', 'b'], 'license': 'AGPL-3'}\n"
        self.assertIn("OCA012", self.codes(self.lint_manifest(bad)))
        self.assertNotIn("OCA012", self.codes(self.lint_manifest(self.GOOD_MANIFEST)))

    def test_oca013_manifest_required_author(self):
        config = Config(manifest_required_authors=["Skysize"])
        bad = "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'Someone Else', 'license': 'AGPL-3'}\n"
        self.assertIn("OCA013", self.codes(self.lint_manifest(bad, config=config)))
        good = "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'Skysize, Someone Else', 'license': 'AGPL-3'}\n"
        self.assertNotIn("OCA013", self.codes(self.lint_manifest(good, config=config)))
        # No required author configured by default
        self.assertNotIn("OCA013", self.codes(self.lint_manifest(bad)))

    def test_oca014_development_status_allowed(self):
        bad = (
            "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3',"
            " 'development_status': 'InvalidStatus'}\n"
        )
        self.assertIn("OCA014", self.codes(self.lint_manifest(bad)))
        good = bad.replace("InvalidStatus", "Beta")
        self.assertNotIn("OCA014", self.codes(self.lint_manifest(good)))

    def test_oca015_manifest_deprecated_key(self):
        bad = (
            "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3',"
            " 'description': 'Use the README instead'}\n"
        )
        self.assertIn("OCA015", self.codes(self.lint_manifest(bad)))
        self.assertNotIn("OCA015", self.codes(self.lint_manifest(self.GOOD_MANIFEST)))

    def test_oca016_manifest_maintainers_list(self):
        bad = (
            "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3',"
            " 'maintainers': 'single-string'}\n"
        )
        self.assertIn("OCA016", self.codes(self.lint_manifest(bad)))
        good = bad.replace("'single-string'", "['someone']")
        self.assertNotIn("OCA016", self.codes(self.lint_manifest(good)))

    def test_oca017_manifest_data_duplicated(self):
        bad = (
            "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3',"
            " 'data': ['views/a.xml', 'views/a.xml']}\n"
        )
        extra = {"views/a.xml": "<odoo/>"}
        self.assertIn("OCA017", self.codes(self.lint_manifest(bad, extra_files=extra)))
        good = "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3', 'data': ['views/a.xml']}\n"
        self.assertNotIn("OCA017", self.codes(self.lint_manifest(good, extra_files=extra)))

    def test_oca018_manifest_behind_migrations(self):
        manifest = "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3'}\n"
        extra = {"migrations/16.0.2.0.0/pre-migration.py": "# migration"}
        self.assertIn("OCA018", self.codes(self.lint_manifest(manifest, extra_files=extra)))
        extra_ok = {"migrations/16.0.1.0.0/pre-migration.py": "# migration"}
        self.assertNotIn("OCA018", self.codes(self.lint_manifest(manifest, extra_files=extra_ok)))

    def test_oca019_manifest_external_assets(self):
        bad = (
            "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3',"
            " 'assets': {'web.assets_backend': ['https://cdn.example.com/lib.js']}}\n"
        )
        self.assertIn("OCA019", self.codes(self.lint_manifest(bad)))
        good = (
            "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3',"
            " 'assets': {'web.assets_backend': ['my_module/static/src/js/lib.js']}}\n"
        )
        extra = {"static/src/js/lib.js": "// js"}
        self.assertNotIn("OCA019", self.codes(self.lint_manifest(good, extra_files=extra)))

    def test_oca020_missing_readme(self):
        self.assertIn("OCA020", self.codes(self.lint_manifest(self.GOOD_MANIFEST)))
        for readme in ("README.rst", "README.md", "README.txt"):
            diagnostics = self.lint_manifest(self.GOOD_MANIFEST, extra_files={readme: "readme"})
            self.assertNotIn("OCA020", self.codes(diagnostics))

    def test_oca021_website_manifest_key_not_valid_uri(self):
        bad = "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3', 'website': 'not a url'}\n"
        self.assertIn("OCA021", self.codes(self.lint_manifest(bad)))
        good = bad.replace("'not a url'", "'https://www.skysize.io'")
        self.assertNotIn("OCA021", self.codes(self.lint_manifest(good)))

    def test_oca022_resource_not_exist(self):
        manifest = (
            "{'name': 'x', 'version': '16.0.1.0.0', 'author': 'a', 'license': 'AGPL-3',"
            " 'data': ['views/missing.xml']}\n"
        )
        self.assertIn("OCA022", self.codes(self.lint_manifest(manifest)))
        extra = {"views/missing.xml": "<odoo/>"}
        self.assertNotIn("OCA022", self.codes(self.lint_manifest(manifest, extra_files=extra)))


if __name__ == "__main__":
    unittest.main()
