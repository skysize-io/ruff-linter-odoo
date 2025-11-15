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
git clone https://github.com/OCA/ruff-linter-odoo.git
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
# Valid Odoo versions to check against
valid-odoo-versions = ["14.0", "15.0", "16.0", "17.0", "18.0"]

# Output format: text, json, sarif, github
output-format = "text"

# Enable/disable specific checks
enable = []  # Empty means all checks enabled
disable = ["OCA001"]  # Disable specific checks

# Manifest checks
manifest-required-authors = ["Odoo Community Association (OCA)"]
license-allowed = [
    "AGPL-3",
    "LGPL-3",
    "GPL-2",
    "GPL-2 or any later version",
    "GPL-3",
    "GPL-3 or any later version",
]
development-status-allowed = ["Alpha", "Beta", "Production/Stable", "Mature"]

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

| Code | Description | Level |
|------|-------------|-------|
| OCA001 | Print used. Use `logger` instead. | Warning |
| OCA002 | Use of cr.commit() directly | Error |
| OCA003 | SQL injection risk. Use parameters | Error |
| OCA004 | Same Odoo module absolute import. Use relative import | Warning |
| OCA005 | `odoo.exceptions.Warning` is deprecated | Refactor |
| OCA006 | Name of compute method should start with "_compute_" | Convention |
| OCA007 | Missing `super` call in method | Warning |
| OCA008 | Use lazy % or .format() in odoo._ functions | Warning |
| OCA009 | Missing required key in manifest file | Convention |
| OCA010 | License not allowed in manifest file | Convention |
| OCA011 | Wrong Version Format in manifest file | Convention |
| OCA012 | The author key must be a string | Error |
| OCA013 | Required author missing in manifest | Convention |
| OCA014 | Invalid development_status in manifest | Convention |

## Pre-commit Hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/OCA/ruff-linter-odoo
    rev: v1.0.0
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

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Credits

This project is maintained by the [skysize.io](https://www.skysize.io/).

Based on the excellent work of [pylint-odoo](https://github.com/OCA/pylint-odoo), modernized for the Ruff era.
