# ruff-linter-odoo

A modern, standalone linting tool for Odoo modules with Ruff-compatible output.

[![Build Status](https://github.com/skysize-io/ruff-linter-odoo/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/skysize-io/ruff-linter-odoo/actions/workflows/test.yml?query=branch%3Amain)
[![version](https://img.shields.io/pypi/v/ruff-linter-odoo.svg)](https://pypi.org/project/ruff-linter-odoo)
[![supported-versions](https://img.shields.io/pypi/pyversions/ruff-linter-odoo.svg)](https://pypi.org/project/ruff-linter-odoo)

## Overview

`ruff-linter-odoo` is a modern, standalone linting tool specifically designed for Odoo modules. Unlike traditional pylint-based solutions, it:

- **Standalone**: No Pylint dependency - uses Python's built-in `ast` module for analysis
- **Ruff-Compatible**: Output formats compatible with Ruff for seamless integration
- **Modern**: Uses `pyproject.toml` for configuration (no `setup.py`)
- **Fast**: Lightweight AST-based analysis
- **Flexible**: Multiple output formats (text, JSON, SARIF, GitHub Actions)

## Installation

```bash
pip install ruff-linter-odoo
```

Or install from source:

```bash
git clone https://github.com/skysize-io/ruff-linter-odoo.git
cd ruff-linter-odoo
pip install -e .
```

## Usage

### Basic Usage

Check current directory:
```bash
ruff-linter-odoo check .
```

Check specific files or directories:
```bash
ruff-linter-odoo check path/to/odoo/addons/
```

### Integration with Ruff

You can use `ruff-linter-odoo` alongside Ruff for comprehensive code quality checks:

```bash
ruff check . && ruff-linter-odoo check .
```

### Output Formats

#### Text (default)
```bash
ruff-linter-odoo check . --format text
```

Output:
```
path/to/file.py:10:4: OCA001 Print used. Use `logger` instead.
path/to/file.py:25:8: OCA002 Use of cr.commit() directly

Found 2 error(s).
```

#### JSON
```bash
ruff-linter-odoo check . --format json
```

#### SARIF (for IDE integration)
```bash
ruff-linter-odoo check . --format sarif
```

#### GitHub Actions
```bash
ruff-linter-odoo check . --format github
```

## Configuration

Configuration is done via `pyproject.toml`:

```toml
[tool.ruff-linter-odoo]
# Valid Odoo versions to check against (used by manifest-version-format and
# to enable version-dependent checks). Defaults to all versions 4.2 - 19.0.
valid-odoo-versions = ["16.0", "17.0", "18.0", "19.0"]

# Output format: text, json, sarif, github
output-format = "text"

# Enable/disable specific checks
enable = []  # Empty means all checks enabled
disable = ["OCA001"]  # Disable specific checks

# Manifest checks
manifest-required-keys = ["name", "version", "author", "license"]
manifest-deprecated-keys = ["description"]
manifest-required-authors = []  # e.g. ["My Company"] to enforce an author
readme-template-url = "https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst"
license-allowed = [
    "AGPL-3",
    "LGPL-3",
    "GPL-2",
    "GPL-2 or any later version",
    "GPL-3",
    "GPL-3 or any later version",
    "OEEL-1",
    "Other OSI approved licence",
    "Other proprietary",
]
development-status-allowed = ["Alpha", "Beta", "Production/Stable", "Mature"]

# Exception classes whose string arguments must be translated (OCA023)
odoo-exceptions = ["UserError", "ValidationError", "AccessError", "Warning"]

# Path patterns to exclude
exclude = [
    ".git",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
    "*.egg-info",
    "build",
    "dist",
]
```

## Available Checks

Codes are sequential (`OCA001`, `OCA002`, ...) and intentionally do **not** mirror
upstream pylint-odoo message ids: upstream ids are only unique together with their
letter prefix (`C8101` and `E8101` are different rules), so a plain numeric mapping
would be ambiguous. If you are migrating from pylint-odoo, use the "pylint-odoo"
column below to find the new code.

| Code | pylint-odoo | Description | Level |
|------|-------------|-------------|-------|
| OCA001 | print-used (W8116) | Print used. Use `logger` instead. | Warning |
| OCA002 | invalid-commit (E8102) | Use of cr.commit() directly | Error |
| OCA003 | sql-injection (E8103) | SQL injection risk. Use parameters | Error |
| OCA004 | odoo-addons-relative-import (W8150) | Same Odoo module absolute import. Use relative import | Warning |
| OCA005 | odoo-exception-warning (R8101) | `odoo.exceptions.Warning` is deprecated | Refactor |
| OCA006 | method-compute (C8108) | Name of compute method should start with "_compute_" | Convention |
| OCA007 | method-required-super (W8106) | Missing `super` call in method | Warning |
| OCA008 | translation-not-lazy (W8301) | % interpolation instead of `_()` arguments | Warning |
| OCA009 | manifest-required-key (C8102) | Missing required key in manifest file | Convention |
| OCA010 | license-allowed (C8105) | License not allowed in manifest file | Convention |
| OCA011 | manifest-version-format (C8106) | Wrong Version Format in manifest file | Convention |
| OCA012 | manifest-author-string (E8101) | The author key must be a string | Error |
| OCA013 | manifest-required-author (C8101) | Required author missing in manifest | Convention |
| OCA014 | development-status-allowed (C8111) | Invalid development_status in manifest | Convention |
| OCA015 | manifest-deprecated-key (C8103) | Deprecated key in manifest file | Convention |
| OCA016 | manifest-maintainers-list (E8104) | maintainers key must be a list of strings | Error |
| OCA017 | manifest-data-duplicated (W8125) | Data file duplicated in manifest | Warning |
| OCA018 | manifest-behind-migrations (E8145) | Manifest version lower than migration scripts | Error |
| OCA019 | manifest-external-assets (W8162) | Asset loaded from an external URL | Warning |
| OCA020 | missing-readme (C8112) | Missing README file next to the manifest | Convention |
| OCA021 | website-manifest-key-not-valid-uri (W8114) | website key is not a valid URI | Warning |
| OCA022 | resource-not-exist (F8101) | Manifest data file does not exist | Error |
| OCA023 | translation-required (C8107) | String parameter requires translation | Convention |
| OCA024 | translation-contains-variable (W8115) | Translatable term contains variables | Warning |
| OCA025 | translation-positional-used (W8120) | Multiple positional placeholders in translation | Warning |
| OCA026 | translation-field (W8103) | `_()` in field definitions is not necessary | Warning |
| OCA027 | translation-format-interpolation (W8302) | str.format() used with `_()` | Warning |
| OCA028 | translation-fstring-interpolation (W8303) | f-string used inside `_()` | Warning |
| OCA029 | translation-format-truncated (E8301) | Translation format string ends mid-specifier | Error |
| OCA030 | translation-too-few-args (E8306) | Not enough arguments for format string | Error |
| OCA031 | translation-too-many-args (E8305) | Too many arguments for format string | Error |
| OCA032 | translation-unsupported-format (E8300) | Unsupported format character | Error |
| OCA033 | prefer-env-translation (W8161) | Prefer `self.env._` (Odoo >= 18) | Warning |
| OCA034 | method-inverse (C8110) | Name of inverse method should start with "_inverse_" | Convention |
| OCA035 | method-search (C8109) | Name of search method should start with "_search_" | Convention |

Unlike upstream, the translation checks (OCA008, OCA027–OCA032) also cover
`_lt()` calls — a lazily-translated string has the same bugs.

`ruff-linter-odoo` only implements Odoo-specific rules. Upstream pylint-odoo also
relied on pylint built-ins for generic checks (eval-used, unused imports, ...);
those are Ruff's job — run `ruff check` alongside this tool (see below).

### Inline suppression

Ruff-style `# noqa` comments are supported:

```python
print("debugging")          # noqa           <- suppresses everything on this line
print("debugging")          # noqa: OCA001   <- suppresses only OCA001
cr.commit()                 # noqa: OCA001, OCA002
```

## Pre-commit Hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/skysize-io/ruff-linter-odoo
    rev: v0.5.0
    hooks:
      - id: ruff-linter-odoo
        args: [check, .]
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run ruff-linter-odoo
  run: |
    pip install ruff-linter-odoo
    ruff-linter-odoo check . --format github
```

### GitLab CI

```yaml
lint:odoo:
  script:
    - pip install ruff-linter-odoo
    - ruff-linter-odoo check . --format text
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Building

```bash
pip install build
python -m build
```

## Comparison with pylint-odoo

| Feature | ruff-linter-odoo | pylint-odoo |
|---------|------------------|-------------|
| Pylint dependency | ❌ No | ✅ Yes |
| Configuration | pyproject.toml | .pylintrc |
| Output formats | Text, JSON, SARIF, GitHub | Pylint format |
| Speed | Fast (AST-based) | Slower (full analysis) |
| Ruff integration | ✅ Compatible | ❌ Different format |
| Modern packaging | ✅ pyproject.toml | ❌ setup.py |

## Migration from pylint-odoo

1. Install `ruff-linter-odoo`:
   ```bash
   pip install ruff-linter-odoo
   ```

2. Update your configuration from `.pylintrc` to `pyproject.toml`:
   ```toml
   [tool.ruff-linter-odoo]
   valid-odoo-versions = ["16.0"]
   ```

3. Update your CI/CD:
   ```bash
   # Old
   pylint --load-plugins=pylint_odoo -e odoolint path/to/test

   # New
   ruff-linter-odoo check path/to/test
   ```

4. Use alongside Ruff:
   ```bash
   ruff check . && ruff-linter-odoo check .
   ```

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/skysize-io/ruff-linter-odoo).

## License

This project is licensed under the AGPL-3.0-or-later License - see the [LICENSE](LICENSE) file for details.

Large parts of the checker logic are derived from [pylint-odoo](https://github.com/OCA/pylint-odoo),
copyright the Odoo Community Association (OCA), also licensed AGPLv3+.

## Credits

This project is maintained by the [skysize.io](https://www.skysize.io/).

Based on the excellent work of [pylint-odoo](https://github.com/OCA/pylint-odoo), modernized for the Ruff era.
