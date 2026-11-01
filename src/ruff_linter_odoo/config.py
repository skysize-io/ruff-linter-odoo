"""Configuration management for ruff-linter-odoo."""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_VALID_ODOO_VERSIONS = [
    "4.2",
    "5.0",
    "6.0",
    "6.1",
    "7.0",
    "8.0",
    "9.0",
    "10.0",
    "11.0",
    "12.0",
    "13.0",
    "14.0",
    "15.0",
    "16.0",
    "17.0",
    "18.0",
    "19.0",
]

# Exception classes from odoo/exceptions.py whose messages must be translated
DEFAULT_ODOO_EXCEPTIONS = [
    "AccessDenied",
    "AccessError",
    "CacheMiss",
    "except_orm",
    "MissingError",
    "RedirectWarning",
    "UserError",
    "ValidationError",
    "Warning",
]


@dataclass
class Config:
    """Configuration for ruff-linter-odoo."""

    # Odoo version settings
    valid_odoo_versions: list[str] = field(default_factory=lambda: list(DEFAULT_VALID_ODOO_VERSIONS))

    # Output settings
    output_format: str = "text"  # text, json, sarif, github

    # Check settings
    enable: list[str] = field(default_factory=list)
    disable: list[str] = field(default_factory=list)

    # Manifest checks: Odoo only requires `name` (license defaults to LGPL-3)
    manifest_required_keys: list[str] = field(default_factory=lambda: ["name"])
    # Values accepted by ir.module.module's license selection
    license_allowed: list[str] = field(
        default_factory=lambda: [
            "AGPL-3",
            "LGPL-3",
            "GPL-2",
            "GPL-2 or any later version",
            "GPL-3",
            "GPL-3 or any later version",
            "OEEL-1",
            "OPL-1",
            "Other OSI approved licence",
            "Other proprietary",
        ]
    )
    # Translation checks
    odoo_exceptions: list[str] = field(default_factory=lambda: list(DEFAULT_ODOO_EXCEPTIONS))

    # Path settings
    exclude: list[str] = field(
        default_factory=lambda: [
            ".git",
            ".tox",
            ".venv",
            "venv",
            "__pycache__",
            "*.egg-info",
            "build",
            "dist",
        ]
    )

    @classmethod
    def from_pyproject_toml(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from pyproject.toml."""
        if path is None:
            path = Path.cwd() / "pyproject.toml"

        if not path.exists():
            return cls()

        with open(path, "rb") as f:
            data = tomllib.load(f)

        tool_config = data.get("tool", {}).get("ruff-linter-odoo", {})

        # Fall back to the dataclass defaults for anything not configured
        default = cls()

        return cls(
            valid_odoo_versions=tool_config.get("valid-odoo-versions", default.valid_odoo_versions),
            output_format=tool_config.get("output-format", default.output_format),
            enable=tool_config.get("enable", default.enable),
            disable=tool_config.get("disable", default.disable),
            manifest_required_keys=tool_config.get("manifest-required-keys", default.manifest_required_keys),
            license_allowed=tool_config.get("license-allowed", default.license_allowed),
            odoo_exceptions=tool_config.get("odoo-exceptions", default.odoo_exceptions),
            exclude=tool_config.get("exclude", default.exclude),
        )

    def is_check_enabled(self, check_code: str) -> bool:
        """Check if a specific check is enabled."""
        if self.enable and check_code not in self.enable:
            return False
        return check_code not in self.disable
