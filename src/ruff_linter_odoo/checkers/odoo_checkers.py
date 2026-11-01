"""Odoo-specific linting checks.

The rules follow the official Odoo coding guidelines, not the OCA ones:
OCA-only conventions (relative imports, required author, README template,
development_status, maintainers, series-prefixed versions) are not checked.

Rule codes (ODO001, ODO002, ...) are stable: a removed rule leaves a gap,
it is never renumbered. Codes ported from pylint-odoo do not mirror its
message ids (C8101 and E8101 are different rules there, so a plain numeric
mapping would be ambiguous); the README documents the mapping.
"""

import ast
import io
import re
import tokenize
from collections import Counter
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, urlsplit

from ..diagnostic import DiagnosticLevel
from ..visitor import BaseChecker

#: Method names that mark a string as translatable (odoo.tools.translate).
TRANSLATION_METHODS = ("_", "_lt")

#: Manifest keys holding lists of data file paths.
MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "test", "update_xml"]

#: Cursor expressions whose commit()/execute() usage is checked.
CURSOR_EXPRESSIONS = (
    "cr",  # old api
    "self._cr",  # new api
    "self.cr",  # controllers and tests
    "self.env.cr",
)

#: Methods that must call super() when overridden.
METHOD_REQUIRED_SUPER = (
    "copy",
    "create",
    "default_get",
    "read",
    "setUp",
    "setUpClass",
    "tearDown",
    "tearDownClass",
    "unlink",
    "write",
)

#: Official Odoo coding guidelines, linked from rule messages.
GUIDELINES_URL = "https://www.odoo.com/documentation/19.0/contributing/development/coding_guidelines.html"

#: Non-ASCII punctuation and its ASCII replacement (Odoo guidelines: plain
#: ASCII punctuation in comments, docstrings and user-facing strings).
NON_ASCII_PUNCTUATION = {
    "\u2014": "a comma, colon, semicolon or parentheses",  # em dash
    "\u2013": "-",  # en dash
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2026": "...",
}
NON_ASCII_PUNCTUATION_RE = re.compile("[" + "".join(NON_ASCII_PUNCTUATION) + "]")

# Based on https://github.com/python-validators/validators domain regex,
# same as upstream pylint-odoo misc.py
DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-_]{0,61}[a-z]$",
    re.IGNORECASE,
)

#: Conversion types accepted by Python's %-formatting.
PRINTF_VALID_CONVERSIONS = "diouxXeEfFgGcrsa"

#: printf-style placeholder pattern (same source as upstream pylint-odoo):
#: https://github.com/translate/translate/blob/9de0d72437/translate/filters/checks.py#L50-L62
PRINTF_PATTERN = re.compile(
    r"""
        %(                          # initial %
        (?P<boost_ord>\d+)%         # boost::format style variable order, like %1%
        |
              (?:(?P<ord>\d+)\$|    # variable order, like %1$s
              \((?P<key>\w+)\))?    # Python style variables, like %(var)s
        (?P<fullvar>
            [+#-]*                  # flags
            (?:\d+)?                # width
            (?:\.\d+)?              # precision
            (hh\|h\|l\|ll)?         # length formatting
            (?P<type>[\w@]))        # type (%s, %d, etc.)
        )""",
    re.VERBOSE,
)


def get_func_name(func: ast.AST) -> str:
    """Return the called name for Name/Attribute nodes ('' otherwise)."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def get_str_value(node: ast.AST) -> Optional[str]:
    """Return the string value of a Constant or (best-effort) JoinedStr node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(value.value if isinstance(value, ast.Constant) else "{}" for value in node.values)
    return None


def get_dotted_name(node: ast.AST) -> str:
    """Return 'self.env.cr' for an attribute chain of Names ('' if not one)."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def parse_printf(fmt: str) -> tuple[int, set[str], Optional[tuple[str, Optional[str]]]]:
    """Parse a %-format string.

    Returns (positional_count, named_keys, error) where error is None,
    ("truncated", None) for a string ending mid-specifier, or
    ("unsupported", char) for an invalid conversion character.
    """
    i = 0
    n = len(fmt)
    count = 0
    keys: set[str] = set()
    while i < n:
        if fmt[i] != "%":
            i += 1
            continue
        i += 1
        if i >= n:
            return count, keys, ("truncated", None)
        if fmt[i] == "%":
            i += 1
            continue
        key = None
        if fmt[i] == "(":
            end = fmt.find(")", i)
            if end < 0:
                return count, keys, ("truncated", None)
            key = fmt[i + 1 : end]
            i = end + 1
        while i < n and fmt[i] in "+-# 0":
            i += 1
        while i < n and (fmt[i].isdigit() or fmt[i] == "*"):
            i += 1
        if i < n and fmt[i] == ".":
            i += 1
            while i < n and (fmt[i].isdigit() or fmt[i] == "*"):
                i += 1
        while i < n and fmt[i] in "hlL":
            i += 1
        if i >= n:
            return count, keys, ("truncated", None)
        conversion = fmt[i]
        if conversion not in PRINTF_VALID_CONVERSIONS:
            return count, keys, ("unsupported", conversion)
        if key is not None:
            keys.add(key)
        else:
            count += 1
        i += 1
    return count, keys, None


def count_format_placeholders(fmt: str) -> int:
    """Count positional str.format() placeholders ('{}', '{0}', ...)."""
    import string as string_mod

    args: list[int] = []
    try:
        for _, name, _, _ in string_mod.Formatter().parse(fmt):
            if name is None:
                continue
            if not name:
                args.append(0)
            elif name.isdigit():
                args.append(int(name) + 1)
    except ValueError:
        return 0
    if not args:
        return 0
    return max(args) or len(args)


class InvalidURL(Exception):  # noqa: N818 - name kept aligned with upstream pylint-odoo
    """Raised by validate_url with a human-readable reason."""


def validate_url(url: str) -> bool:
    """Validate a website URL the same way upstream pylint-odoo does."""
    if not url:
        raise InvalidURL("Empty URL")
    if re.search(r"\s", url):
        raise InvalidURL("URL must not contain white spaces, they must be encoded")
    try:
        scheme, netloc, _path, _query, _fragment = urlsplit(url)
    except ValueError as ve_exc:
        raise InvalidURL(f"URL invalid: {str(ve_exc)}") from ve_exc
    if scheme not in ("https", "http"):
        raise InvalidURL("URL needs to start with 'http[s]://'")
    if not netloc:
        raise InvalidURL("Invalid URL domain not identified")
    if re.search(r"__+", netloc):
        raise InvalidURL(f"Domain section must not contain double underscore '__' because of security issues {netloc}")
    try:
        netloc = netloc.encode("idna").decode("utf-8")
    except UnicodeError as err:
        raise InvalidURL(f"Unable to encode/decode domain section {netloc}") from err
    if not DOMAIN_RE.match(netloc):
        raise InvalidURL(f"Domain '{netloc}' contains invalid characters")
    return True


def version2tuple(version: str) -> tuple[int, ...]:
    """Parse '19.0.1.0.0' into (19, 0, 1, 0, 0); raises ValueError if invalid."""
    return tuple(int(part) for part in version.split("."))


def newest_odoo_version(config) -> Optional[str]:
    """Newest configured Odoo series ('19.0'), None if none parses."""
    versions = []
    for version in config.valid_odoo_versions:
        try:
            versions.append((version2tuple(str(version)), str(version)))
        except ValueError:
            continue
    return max(versions)[1] if versions else None


def odoo_version_at_least(config, minimum: tuple[int, int]) -> bool:
    """True when the newest configured Odoo version is >= minimum."""
    newest = newest_odoo_version(config)
    return newest is None or version2tuple(newest) >= minimum


def full_module_version(version: str, series: str) -> str:
    """Prefix a module version with the series, like odoo.modules.adapt_version.

    '1.0' -> '19.0.1.0'; '19.0.1.0' stays as is.
    """
    if version == series or not version.startswith(series + "."):
        return f"{series}.{version}"
    return version


class PrintChecker(BaseChecker):
    """Check for print statements (should use logger instead)."""

    def visit_Call(self, node: ast.Call):
        """Check for print() calls."""
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            self.add_diagnostic(
                "ODO001",
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
            and get_dotted_name(node.func.value) in CURSOR_EXPRESSIONS
        ):
            self.add_diagnostic(
                "ODO002",
                f"Use of cr.commit() directly - More info {GUIDELINES_URL}#never-commit-the-transaction",
                node,
                DiagnosticLevel.ERROR,
            )
        self.generic_visit(node)


class SQLInjectionChecker(BaseChecker):
    """Check for potential SQL injection vulnerabilities.

    Port of pylint-odoo's sql-injection (E8103): flags cr.execute() /
    cr.executemany() whose query string is built with %, +, str.format()
    or f-strings from non-constant values. Constants, private attributes
    (self._table) and psycopg2.sql wrappers are allowed.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._psycopg2_imported_names: set[str] = set()
        self._function_stack: list[ast.AST] = []

    def visit_Module(self, node: ast.Module):
        """Collect names imported from psycopg2 before checking calls."""
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.ImportFrom):
                if stmt.module and stmt.module.split(".")[0] == "psycopg2":
                    for alias in stmt.names:
                        self._psycopg2_imported_names.add(alias.asname or alias.name)
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    if alias.name.split(".")[0] == "psycopg2":
                        self._psycopg2_imported_names.add((alias.asname or alias.name).split(".")[0])
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._function_stack.append(node)
        self.generic_visit(node)
        self._function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815 - ast.NodeVisitor naming

    def visit_Call(self, node: ast.Call):
        """Check for execute()/executemany() calls with risky formatting."""
        if self._is_sql_injection_risky(node):
            self.add_diagnostic(
                "ODO003",
                f"SQL injection risk. Use parameters if you can. - More info {GUIDELINES_URL}#no-sql-injection",
                node,
                DiagnosticLevel.ERROR,
            )
        self.generic_visit(node)

    def _is_sql_injection_risky(self, node: ast.Call) -> bool:
        if not (
            node.args
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("execute", "executemany")
            and get_dotted_name(node.func.value) in CURSOR_EXPRESSIONS
            # cr.execute("select * from %s" % foo, [bar]) -> probably a good
            # reason for string formatting
            and len(node.args) <= 1
            # ignore in test files, probably not accessible
            and not Path(self.filename).name.startswith("test_")
        ):
            return False
        first_arg = node.args[0]
        if self._node_risky(first_arg):
            return True
        # If the first parameter is a variable, check how it was built instead
        return any(self._node_risky(assigned) for assigned in self._assignation_nodes(first_arg))

    def _node_risky(self, node: ast.AST) -> bool:
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
            if isinstance(node.right, ast.Tuple):
                # execute("..." % (self._table, thing))
                if not all(map(self._allowable, node.right.elts)):
                    return True
            elif isinstance(node.right, ast.Dict):
                # execute("..." % {'table': self._table})
                if not all(self._allowable(v) for v in node.right.values):
                    return True
            elif not self._allowable(node.right):
                # execute("..." % self._table)
                return True
            # 'SELECT ' + operator + ' FROM table' -> recurse into the left side
            if not self._allowable(node.left) and self._node_risky(node.left):
                return True

        # execute("...".format(self._table, table=self._table)); sql.SQL().format is OK
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            if not all(map(self._allowable, node.args or [])):
                return True
            if not all(self._allowable(keyword.value) for keyword in (node.keywords or [])):
                return True

        # f-strings
        if isinstance(node, ast.JoinedStr):
            return not all(self._allowable(value) for value in node.values)

        return False

    def _allowable(self, node: ast.AST) -> bool:
        # sql.SQL or sql.Identifier is OK
        if self._is_psycopg2_sql(node):
            return True
        if isinstance(node, ast.FormattedValue):
            return self._allowable(node.value)
        if isinstance(node, ast.Call):
            node = node.func
        # self._thing is OK (mostly self._table), self._thing() also because
        # it's a common pattern of reports (self._select, self._group_by, ...)
        return (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.attr.startswith("_")
            # cr.execute('SELECT * FROM %s' % 'table') is OK: constants
            # can not be injected
            or isinstance(node, ast.Constant)
        )

    def _is_psycopg2_sql(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return any(self._is_psycopg2_sql(assigned) for assigned in self._assignation_nodes(node))
        if not isinstance(node, ast.Call) or not isinstance(node.func, (ast.Attribute, ast.Name)):
            return False
        dotted = get_dotted_name(node.func) or get_func_name(node.func)
        imported_name = dotted.split(".")[0]
        return imported_name in self._psycopg2_imported_names

    def _assignation_nodes(self, node: ast.AST):
        """Yield values assigned to this Name/Subscript in the current function."""
        if not isinstance(node, (ast.Name, ast.Subscript)) or not self._function_stack:
            return
        try:
            node_repr = ast.unparse(node)
        except Exception:  # defensive: unparse of synthetic nodes
            return
        for stmt in ast.walk(self._function_stack[-1]):
            if (
                isinstance(stmt, ast.Assign)
                and stmt.targets
                and isinstance(stmt.targets[0], (ast.Name, ast.Subscript))
                and ast.unparse(stmt.targets[0]) == node_repr
            ):
                yield stmt.value


class ImportChecker(BaseChecker):
    """Check for Odoo-specific import issues."""

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Check for the deprecated odoo.exceptions.Warning import."""
        if node.module == "odoo.exceptions":
            for alias in node.names:
                if alias.name == "Warning":
                    self.add_diagnostic(
                        "ODO005",
                        "`odoo.exceptions.Warning` is a deprecated alias to `odoo.exceptions.UserError` "
                        "use `from odoo.exceptions import UserError`",
                        node,
                        DiagnosticLevel.REFACTOR,
                    )
        self.generic_visit(node)


class MethodChecker(BaseChecker):
    """Check Odoo method naming conventions and required super() calls."""

    #: field keyword -> (code, expected method name prefix)
    FIELD_METHOD_KEYWORDS = {
        "compute": ("ODO006", "_compute_"),
        "inverse": ("ODO034", "_inverse_"),
        "search": ("ODO035", "_search_"),
    }

    def visit_ClassDef(self, node: ast.ClassDef):
        """Check methods that must call super()."""
        for method in node.body:
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name in METHOD_REQUIRED_SUPER:
                self._check_method_super(method)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Check compute/inverse/search method names in field definitions."""
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "fields"
        ):
            for keyword in node.keywords:
                spec = self.FIELD_METHOD_KEYWORDS.get(keyword.arg or "")
                value = get_str_value(keyword.value) if spec else None
                if spec and value is not None and not value.startswith(spec[1]):
                    self.add_diagnostic(
                        spec[0],
                        f'Name of {keyword.arg} method should start with "{spec[1]}"',
                        keyword.value,
                        DiagnosticLevel.CONVENTION,
                    )
        self.generic_visit(node)

    def _check_method_super(self, node: ast.FunctionDef):
        """Check if the method calls super()."""
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "super":
                return
        self.add_diagnostic(
            "ODO007",
            f'Missing `super` call in "{node.name}" method.',
            node,
            DiagnosticLevel.WARNING,
        )


class TranslationChecker(BaseChecker):
    """Check for translation-related issues in odoo._ / odoo._lt calls."""

    def visit_Call(self, node: ast.Call):
        """Check translation calls."""
        func_name = get_func_name(node.func)

        # _('...').format(...) -> translation-format-interpolation
        if (
            func_name == "format"
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Call)
            and get_func_name(node.func.value.func) in TRANSLATION_METHODS
        ):
            self.add_diagnostic(
                "ODO027",
                "Use of str.format() on the result of odoo._. "
                'Pass the values as arguments to _() instead, e.g. `_("Total: %s", value)`',
                node,
                DiagnosticLevel.WARNING,
            )

        if func_name in TRANSLATION_METHODS and node.args:
            self._check_translation_call(node)

        # message_post(body='literal') -> translation-required
        if (
            func_name == "message_post"
            and isinstance(node.func, ast.Attribute)
            and Path(self.filename).resolve().parent.name != "tests"
        ):
            self._check_message_post(node)

        # fields.X(..., string=_('...')) -> translation-field
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "fields"
        ):
            for argument in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(argument, ast.Call) and get_func_name(argument.func) in TRANSLATION_METHODS:
                    self.add_diagnostic(
                        "ODO026",
                        'Translation method _("string") in fields is not necessary.',
                        argument,
                        DiagnosticLevel.WARNING,
                    )

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        """Check _('...') % values -> interpolation after (outside) translation."""
        if (
            isinstance(node.op, ast.Mod)
            and isinstance(node.left, ast.Call)
            and get_func_name(node.left.func) in TRANSLATION_METHODS
            and self._odoo_version_at_least((14, 0))
        ):
            self.add_diagnostic(
                "ODO008",
                "Use of % interpolation on the result of odoo._. "
                'Pass the values as arguments to _() instead, e.g. `_("Total: %s", value)`',
                node,
                DiagnosticLevel.WARNING,
            )
        self.generic_visit(node)

    def _check_message_post(self, node: ast.Call):
        """Check message_post() body/subject values are translated."""
        for arg in list(node.args) + list(node.keywords):
            if isinstance(arg, ast.keyword):
                keyword = arg.arg or ""
                value = arg.value
            else:
                keyword = ""
                value = arg
            if keyword and keyword not in ("subject", "body"):
                continue
            as_string = ""
            # case: message_post(body='String')
            if isinstance(value, ast.JoinedStr) or (isinstance(value, ast.Constant) and isinstance(value.value, str)):
                as_string = ast.unparse(value)
            # case: message_post(body='String %s' % (...))
            elif (
                isinstance(value, ast.BinOp)
                and isinstance(value.op, ast.Mod)
                and (
                    isinstance(value.left, ast.JoinedStr)
                    or (isinstance(value.left, ast.Constant) and isinstance(value.left.value, str))
                )
                # The right part is translatable only if it is a
                # function or a list of functions
                and not (
                    isinstance(value.right, (ast.Call, ast.Tuple, ast.List))
                    and all(isinstance(child, ast.Call) for child in getattr(value.right, "elts", []))
                )
            ):
                as_string = ast.unparse(value.left)
            # case: message_post(body='String {...}'.format(...))
            elif (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr == "format"
                and (
                    isinstance(value.func.value, ast.JoinedStr)
                    or (isinstance(value.func.value, ast.Constant) and isinstance(value.func.value.value, str))
                )
            ):
                as_string = ast.unparse(value.func.value)
            if as_string:
                keyword_prefix = f"{keyword}=" if keyword else ""
                tl_method = "self.env._" if self._odoo_version_at_least((18, 0)) else "_"
                self.add_diagnostic(
                    "ODO023",
                    f'String parameter on "message_post" requires translation. '
                    f"Use {keyword_prefix}{tl_method}({as_string})",
                    node,
                    DiagnosticLevel.CONVENTION,
                )

    def visit_Raise(self, node: ast.Raise):
        """Check raise UserError('literal') -> translation-required."""
        expr = node.exc
        if isinstance(expr, ast.Call) and expr.args and get_func_name(expr.func) in self.config.odoo_exceptions:
            argument = expr.args[0]
            if (
                isinstance(argument, ast.Call)
                and isinstance(argument.func, ast.Attribute)
                and argument.func.attr == "format"
            ):
                argument = argument.func.value
            elif isinstance(argument, ast.BinOp):
                argument = argument.left
            if get_str_value(argument) is not None:
                exc_name = get_func_name(expr.func)
                tl_method = "self.env._" if self._odoo_version_at_least((18, 0)) else "_"
                self.add_diagnostic(
                    "ODO023",
                    f'String parameter on "{exc_name}" requires translation. Use {tl_method}({ast.unparse(argument)})',
                    node,
                    DiagnosticLevel.CONVENTION,
                )
        self.generic_visit(node)

    def _odoo_version_at_least(self, minimum: tuple[int, int]) -> bool:
        return odoo_version_at_least(self.config, minimum)

    def _check_translation_call(self, node: ast.Call):
        """Run all checks on a _(...) / _lt(...) call."""
        # prefer-env-translation (Odoo >= 18 only): bare _() instead of self.env._()
        if isinstance(node.func, ast.Name) and self._odoo_version_at_least((18, 0)):
            self.add_diagnostic(
                "ODO033",
                "Better using self.env._ More info at https://github.com/odoo/odoo/pull/174844",
                node,
                DiagnosticLevel.WARNING,
            )

        arg = node.args[0]

        # translation-fstring-interpolation: _(f"...")
        if isinstance(arg, ast.JoinedStr):
            self.add_diagnostic(
                "ODO028",
                "Use of f-string inside odoo._. The translation lookup happens on the "
                "interpolated string and will fail; pass the values as arguments to _() instead.",
                node,
                DiagnosticLevel.WARNING,
            )

        # translation-not-lazy + translation-contains-variable: _('...' % values)
        if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod):
            if self._odoo_version_at_least((14, 0)):
                self.add_diagnostic(
                    "ODO008",
                    "Use of % interpolation inside odoo._. "
                    'Pass the values as arguments to _() instead, e.g. `_("Total: %s", value)`',
                    node,
                    DiagnosticLevel.WARNING,
                )
            wrong = f"{ast.unparse(arg.left)} % {ast.unparse(arg.right)}"
            right = f"_({ast.unparse(arg.left)}) % {ast.unparse(arg.right)}"
            self.add_diagnostic(
                "ODO024",
                f'Translatable term in "{wrong}" contains variables. Use {right} instead',
                node,
                DiagnosticLevel.WARNING,
            )
        # translation-format-interpolation + contains-variable: _('...'.format(...))
        elif (
            isinstance(arg, ast.Call)
            and isinstance(arg.func, ast.Attribute)
            and arg.func.attr == "format"
            and isinstance(arg.func.value, ast.Constant)
        ):
            self.add_diagnostic(
                "ODO027",
                "Use of str.format() inside odoo._. "
                'Pass the values as arguments to _() instead, e.g. `_("Total: %s", value)`',
                node,
                DiagnosticLevel.WARNING,
            )
            params = ", ".join(
                [ast.unparse(x) for x in arg.args] + [f"{kw.arg}={ast.unparse(kw.value)}" for kw in arg.keywords]
            )
            wrong = ast.unparse(arg)
            right = f"_({ast.unparse(arg.func.value)}).format({params})"
            self.add_diagnostic(
                "ODO024",
                f'Translatable term in "{wrong}" contains variables. Use {right} instead',
                node,
                DiagnosticLevel.WARNING,
            )

        # translation-positional-used: multiple positional placeholders.
        # Like upstream, this looks at the source text of the whole first
        # argument, so `_('%s %s' % (a, b))` also counts.
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            str2translate = arg.value
        else:
            try:
                str2translate = ast.unparse(arg)
            except Exception:  # defensive: unparse can fail on odd trees
                str2translate = ""
        positional_count, _positional_keys, _positional_error = parse_printf(str2translate.replace("%%", ""))
        format_count = count_format_placeholders(str2translate)
        if positional_count >= 2 or format_count >= 2:
            self.add_diagnostic(
                "ODO025",
                f"Translation method _({str2translate!r}) is using positional string printf formatting with "
                'multiple arguments. Use named placeholder `_("%(placeholder)s")` instead.',
                node,
                DiagnosticLevel.WARNING,
            )

        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            return
        fmt = arg.value
        printf_count, printf_keys, printf_error = parse_printf(fmt)

        # Format-string validity checks only apply when interpolation
        # arguments are supplied: _("...", arg1, ...)
        supplied_args = len(node.args) - 1
        if supplied_args <= 0:
            return
        if printf_error is not None:
            kind, char = printf_error
            if kind == "truncated":
                self.add_diagnostic(
                    "ODO029",
                    "odoo._ format string ends in middle of conversion specifier",
                    node,
                    DiagnosticLevel.ERROR,
                )
            else:
                self.add_diagnostic(
                    "ODO032",
                    f"Unsupported odoo._ format character {char!r} in format string {fmt!r}",
                    node,
                    DiagnosticLevel.ERROR,
                )
            return
        if printf_keys and not printf_count:
            # Named placeholders take a dict argument; skip the count checks.
            return
        if supplied_args > printf_count:
            self.add_diagnostic(
                "ODO031",
                "Too many arguments for odoo._ format string",
                node,
                DiagnosticLevel.ERROR,
            )
        elif supplied_args < printf_count:
            self.add_diagnostic(
                "ODO030",
                "Not enough arguments for odoo._ format string",
                node,
                DiagnosticLevel.ERROR,
            )


class ManifestChecker(BaseChecker):
    """Check Odoo manifest files."""

    def visit_Module(self, node: ast.Module):
        """Check the manifest file structure."""
        manifest_node = self._find_manifest_dict_node(node)
        if manifest_node is None:
            return

        manifest_dict = self._dict_to_python(manifest_node)
        self._key_nodes: dict[str, ast.AST] = {}
        self._value_nodes: dict[str, ast.AST] = {}
        for key, value in zip(manifest_node.keys, manifest_node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self._key_nodes[key.value] = key
                self._value_nodes[key.value] = value

        self._check_required_keys(manifest_dict, node)
        self._check_license(manifest_dict, node)
        self._check_version_format(manifest_dict, node)
        self._check_author(manifest_dict, node)
        self._check_data_files(manifest_dict, node)
        self._check_behind_migrations(manifest_dict, node)
        self._check_external_assets(manifest_dict, node)
        self._check_website(manifest_dict, node)

        self.generic_visit(node)

    def _key_node(self, key: str, default: ast.AST) -> ast.AST:
        """Node of the manifest key for diagnostics, or the given default."""
        return self._key_nodes.get(key, default)

    def _module_dir(self) -> Path:
        """Directory containing the manifest file."""
        return Path(self.filename).resolve().parent

    def _find_manifest_dict_node(self, node: ast.Module) -> Optional[ast.Dict]:
        """Find the manifest dictionary AST node."""
        for item in node.body:
            if isinstance(item, ast.Assign):
                if isinstance(item.value, ast.Dict):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            return item.value
            elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Dict):
                # Standalone dict (common in manifest files)
                return item.value
        return None

    def _dict_to_python(self, node: ast.Dict) -> dict[str, Any]:
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
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self._get_constant_value(elt) for elt in node.elts]
        if isinstance(node, ast.Dict):
            return self._dict_to_python(node)
        return None

    def _check_required_keys(self, manifest: dict[str, Any], node: ast.AST):
        """Check for required manifest keys."""
        for key in self.config.manifest_required_keys:
            if key not in manifest:
                self.add_diagnostic(
                    "ODO009",
                    f'Missing required key "{key}" in manifest file',
                    node,
                    DiagnosticLevel.CONVENTION,
                )

    def _check_license(self, manifest: dict[str, Any], node: ast.AST):
        """Check if license is allowed."""
        license_value = manifest.get("license")
        if license_value and license_value not in self.config.license_allowed:
            self.add_diagnostic(
                "ODO010",
                f'License "{license_value}" not allowed in manifest file.',
                self._key_node("license", node),
                DiagnosticLevel.CONVENTION,
            )

    def _check_version_format(self, manifest: dict[str, Any], node: ast.AST):
        """Check the version is x.y[.z], optionally prefixed by a valid Odoo series.

        Odoo prefixes a bare version with the running series at load time
        (odoo.modules.adapt_version), so '1.0' and '19.0.1.0' are both valid.
        """
        version = manifest.get("version")
        if version:
            valid_versions = "|".join(re.escape(str(v)) for v in self.config.valid_odoo_versions)
            pattern = rf"^(({valid_versions})\.)?\d+\.\d+(\.\d+)?$"
            if not re.match(pattern, str(version)):
                self.add_diagnostic(
                    "ODO011",
                    f'Wrong Version Format "{version}" in manifest file. Regex to match: "{pattern}"',
                    self._key_node("version", node),
                    DiagnosticLevel.CONVENTION,
                )

    def _check_author(self, manifest: dict[str, Any], node: ast.AST):
        """Check author field."""
        author = manifest.get("author")
        if author and not isinstance(author, str):
            self.add_diagnostic(
                "ODO012",
                "The author key in the manifest file must be a string (with comma separated values)",
                self._key_node("author", node),
                DiagnosticLevel.ERROR,
            )

    def _check_data_files(self, manifest: dict[str, Any], node: ast.AST):
        """Check duplicated and missing data files (data/demo/... keys)."""
        module_dir = self._module_dir()
        for key in MANIFEST_DATA_KEYS:
            if key not in manifest:
                continue
            value_node = self._value_nodes.get(key)
            resource_nodes: dict[str, list[ast.AST]] = {}
            if isinstance(value_node, (ast.List, ast.Tuple)):
                for elt in value_node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        resource_nodes.setdefault(elt.value, []).append(elt)
            resources = [r for r in (manifest.get(key) or []) if isinstance(r, str)]
            for resource, coincidences in Counter(resources).items():
                nodes_for_resource = resource_nodes.get(resource) or [node]
                first_node = nodes_for_resource[0]
                if coincidences >= 2:
                    lines_str = ", ".join(str(getattr(n, "lineno", "?")) for n in nodes_for_resource[1:])
                    self.add_diagnostic(
                        "ODO017",
                        f'The file "{resource}" is duplicated in lines {lines_str} from manifest key "{key}"',
                        first_node,
                        DiagnosticLevel.WARNING,
                    )
                if not (module_dir / resource).is_file():
                    self.add_diagnostic(
                        "ODO022",
                        f'File "{key}": "{resource}" not found.',
                        first_node,
                        DiagnosticLevel.ERROR,
                    )

    def _check_behind_migrations(self, manifest: dict[str, Any], node: ast.AST):
        """Check the manifest version is not behind the migration scripts."""
        version = manifest.get("version")
        series = newest_odoo_version(self.config)
        if not version or not series:
            return
        migrations_dir = self._module_dir() / "migrations"
        if not migrations_dir.is_dir():
            return
        # Compare like Odoo does: both sides prefixed with the series
        try:
            version_tuple = version2tuple(full_module_version(str(version), series))
        except ValueError:
            return
        for migration_path in sorted(migrations_dir.iterdir(), reverse=True):
            if not migration_path.is_dir():
                continue
            try:
                migration_tuple = version2tuple(full_module_version(migration_path.name, series))
            except ValueError:
                continue
            if migration_tuple > version_tuple:
                self.add_diagnostic(
                    "ODO018",
                    f"Manifest version ({version}) is lower than migration scripts ({migration_path.name})",
                    self._key_node("version", node),
                    DiagnosticLevel.ERROR,
                )
                break

    def _check_external_assets(self, manifest: dict[str, Any], node: ast.AST):
        """Check no assets are loaded from external URLs."""
        assets_node = self._value_nodes.get("assets")
        if not isinstance(assets_node, ast.Dict):
            return

        def is_external_url(url: Any) -> bool:
            return isinstance(url, str) and bool(urlparse(url).scheme)

        for bundle_value in assets_node.values:
            for element in getattr(bundle_value, "elts", []):
                if isinstance(element, ast.Constant) and is_external_url(element.value):
                    self.add_diagnostic(
                        "ODO019",
                        f"Asset {element.value} should be distributed with module's source code. "
                        "More info at https://httptoolkit.com/blog/public-cdn-risks/",
                        element,
                        DiagnosticLevel.WARNING,
                    )
                elif isinstance(element, (ast.Tuple, ast.List)):
                    for entry in element.elts:
                        if isinstance(entry, ast.Constant) and is_external_url(entry.value):
                            self.add_diagnostic(
                                "ODO019",
                                f"Asset {entry.value} should be distributed with module's source code. "
                                "More info at https://httptoolkit.com/blog/public-cdn-risks/",
                                element,
                                DiagnosticLevel.WARNING,
                            )

    def _check_website(self, manifest: dict[str, Any], node: ast.AST):
        """Check the website key is a valid URI."""
        website = manifest.get("website") or ""
        if not isinstance(website, str):
            return
        msg = ""
        url_is_valid = False
        try:
            url_is_valid = validate_url(website)
        except InvalidURL as url_exc:
            msg = str(url_exc)
        if website and not url_is_valid:
            self.add_diagnostic(
                "ODO021",
                f'Website "{website}" in manifest key is not a valid URI. {msg}',
                self._key_node("website", node),
                DiagnosticLevel.WARNING,
            )


class ModuleLevelTranslationChecker(BaseChecker):
    """Check _() is not called at module or class level (runs at import time)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._function_depth = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Decorators and default values are evaluated at definition time
        for child in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if child is not None:
                self.visit(child)
        self._function_depth += 1
        for child in node.body:
            self.visit(child)
        self._function_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815 - ast.NodeVisitor naming

    def visit_Lambda(self, node: ast.Lambda):
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_Call(self, node: ast.Call):
        if not self._function_depth and isinstance(node.func, ast.Name) and node.func.id == "_":
            self.add_diagnostic(
                "ODO036",
                "_() called at module or class level runs at import time, without the user's language. "
                'Translate inside the method, or use `_lt = LazyTranslate(__name__)` and `_lt("...")`.',
                node,
                DiagnosticLevel.WARNING,
            )
        self.generic_visit(node)


class RouteChecker(BaseChecker):
    """Check controller route declarations."""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call) and get_func_name(decorator.func) == "route"):
                continue
            for keyword in decorator.keywords:
                if (
                    keyword.arg == "type"
                    and get_str_value(keyword.value) == "json"
                    and odoo_version_at_least(self.config, (19, 0))
                ):
                    self.add_diagnostic(
                        "ODO037",
                        "type='json' is a deprecated alias of type='jsonrpc' since Odoo 19.0.",
                        keyword.value,
                        DiagnosticLevel.WARNING,
                    )
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815 - ast.NodeVisitor naming


class PunctuationChecker(BaseChecker):
    """Check comments, docstrings and user-facing strings use ASCII punctuation."""

    def visit_Module(self, node: ast.Module):
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(self.source_code).readline))
        except (tokenize.TokenError, SyntaxError):
            tokens = []
        for token in tokens:
            if token.type == tokenize.COMMENT:
                self._check_text(token.string, token.start[0], token.start[1])
        self._check_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._check_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_docstring(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815 - ast.NodeVisitor naming

    def visit_Call(self, node: ast.Call):
        """Translated terms and Odoo exception messages are user-facing."""
        func_name = get_func_name(node.func)
        if node.args and (func_name in TRANSLATION_METHODS or func_name in self.config.odoo_exceptions):
            argument = node.args[0]
            text = get_str_value(argument)
            if text is not None:
                self._check_text(text, argument.lineno, argument.col_offset)
        self.generic_visit(node)

    def _check_docstring(self, node: ast.AST):
        body = getattr(node, "body", None)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            self._check_text(body[0].value.value, body[0].lineno, body[0].col_offset)

    def _check_text(self, text: str, line: int, column: int):
        found = sorted(set(NON_ASCII_PUNCTUATION_RE.findall(text)))
        if not found:
            return
        hints = "; ".join(f"{char!r} -> {NON_ASCII_PUNCTUATION[char]}" for char in found)
        location = ast.Constant(value=None, lineno=line, col_offset=column)
        self.add_diagnostic(
            "ODO038",
            f"Use plain ASCII punctuation in comments, docstrings and user-facing strings: {hints}",
            location,
            DiagnosticLevel.CONVENTION,
        )
