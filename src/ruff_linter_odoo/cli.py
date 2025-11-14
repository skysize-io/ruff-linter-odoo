"""Command-line interface for ruff-linter-odoo."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Config
from .formatters import get_formatter
from .linter import Linter


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="A modern, standalone linting tool for Odoo modules with Ruff-compatible output",
        prog="ruff-linter-odoo",
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 'check' command (similar to ruff check)
    check_parser = subparsers.add_parser("check", help="Check files for linting errors")
    check_parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to check (default: current directory)",
    )
    check_parser.add_argument(
        "--format",
        choices=["text", "json", "sarif", "github"],
        default=None,
        help="Output format (default: text)",
    )
    check_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to pyproject.toml configuration file",
    )
    check_parser.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore configuration file",
    )

    # Parse arguments
    args = parser.parse_args()

    # Default to 'check' command if none specified
    if args.command is None:
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            # Assume first argument is a path
            args.command = "check"
            args.paths = sys.argv[1:]
            args.format = None
            args.config = None
            args.no_config = False
        else:
            parser.print_help()
            return 0

    if args.command == "check":
        return run_check(args)

    return 0


def run_check(args):
    """Run the check command."""
    # Load configuration
    if args.no_config:
        config = Config()
    else:
        config_path = args.config or Path.cwd() / "pyproject.toml"
        config = Config.from_pyproject_toml(config_path)

    # Override format if specified in CLI
    if args.format:
        config.output_format = args.format

    # Create linter
    linter = Linter(config)

    # Collect all diagnostics
    all_diagnostics = []
    for path_str in args.paths:
        path = Path(path_str)
        if not path.exists():
            print(f"Error: Path does not exist: {path}", file=sys.stderr)
            return 1

        diagnostics = linter.lint_path(path)
        all_diagnostics.extend(diagnostics)

    # Format and output results
    formatter = get_formatter(config.output_format)
    output = formatter.format(all_diagnostics)

    if output:
        print(output)

    # Return exit code based on results
    # Return non-zero if there are errors
    has_errors = any(d.level.value == "error" for d in all_diagnostics)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
