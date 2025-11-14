"""Configuration management for ruff-linter-odoo."""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class Config:
    """Configuration for ruff-linter-odoo."""

    # Odoo version settings
    valid_odoo_versions: List[str] = field(
        default_factory=lambda: ["14.0", "15.0", "16.0", "17.0", "18.0"]
    )

    # Output settings
    output_format: str = "text"  # text, json, sarif, github

    # Check settings
    enable: List[str] = field(default_factory=list)
    disable: List[str] = field(default_factory=list)

    # Manifest checks
    manifest_required_authors: List[str] = field(
        default_factory=lambda: ["Odoo Community Association (OCA)"]
    )
    license_allowed: List[str] = field(
        default_factory=lambda: [
            "AGPL-3",
            "LGPL-3",
            "GPL-2",
            "GPL-2 or any later version",
            "GPL-3",
            "GPL-3 or any later version",
        ]
    )
    development_status_allowed: List[str] = field(
        default_factory=lambda: ["Alpha", "Beta", "Production/Stable", "Mature"]
    )

    # Path settings
    exclude: List[str] = field(
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

        # Create default instance first
        default = cls()

        return cls(
            valid_odoo_versions=tool_config.get(
                "valid-odoo-versions", default.valid_odoo_versions
            ),
            output_format=tool_config.get("output-format", "text"),
            enable=tool_config.get("enable", []),
            disable=tool_config.get("disable", []),
            manifest_required_authors=tool_config.get(
                "manifest-required-authors",
                ["Odoo Community Association (OCA)"],
            ),
            license_allowed=tool_config.get(
                "license-allowed",
                [
                    "AGPL-3",
                    "LGPL-3",
                    "GPL-2",
                    "GPL-2 or any later version",
                    "GPL-3",
                    "GPL-3 or any later version",
                ],
            ),
            development_status_allowed=tool_config.get(
                "development-status-allowed",
                ["Alpha", "Beta", "Production/Stable", "Mature"],
            ),
            exclude=tool_config.get(
                "exclude",
                [
                    ".git",
                    ".tox",
                    ".venv",
                    "venv",
                    "__pycache__",
                    "*.egg-info",
                    "build",
                    "dist",
                ],
            ),
        )

    def is_check_enabled(self, check_code: str) -> bool:
        """Check if a specific check is enabled."""
        if self.enable and check_code not in self.enable:
            return False
        if check_code in self.disable:
            return False
        return True
