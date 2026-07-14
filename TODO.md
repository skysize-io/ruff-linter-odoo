# ruff-linter-odoo — Work Plan

State as of 2026-07-14: 35 of ~63 upstream pylint-odoo rules implemented, per-rule
counts pinned against `testing/resources/test_repo` (validated against upstream's
reference numbers from commit `0a98430`), `# noqa` support in, metadata fixed,
stale branches deleted. `ruff check`, `ruff format --check` and all 51 tests pass.

The original v1-usable checklist is DONE except the PyPI registration (manual step):

1. [x] Metadata correct, stale branches gone (items 1, 3)
2. [x] Tests assert real counts, one focused test per rule (item 2)
3. [x] 4a (manifest checks) + the translation family from 4b ported
4. [x] `# noqa` support
5. [x] Dogfood against webapp-odoo custom modules — 23 justified findings, no
       false-positive storm, no crashes (see "Dogfood notes" below)

---

## 1. Fix package metadata — DONE 2026-07-14

- [x] `authors` → Skysize
- [x] `[project.urls]` → github.com/skysize-io/ruff-linter-odoo (also formatters.py SARIF URL)
- [x] License: AGPL-3.0-or-later confirmed (upstream pylint-odoo is AGPLv3+, this is a
      derived work). The LICENSE file was wrongly MIT (GitHub repo template) — replaced
      with the full AGPL text; attribution note added to the README Credits/License.
- [x] Remaining OCA references removed (the odoo-community.org CONTRIBUTING links in
      rule messages are intentional — they match upstream message text)
- [x] Bonus: requires-python >= 3.9 (ast.unparse), stale `src/pylint_odoo` pycache and
      broken pbr `ChangeLog` removed, README CONTRIBUTING.md dead link fixed

## 2. Make the test suite honest — DONE 2026-07-14

- [x] Real per-rule counts pinned in `tests/test_main.py` `EXPECTED_DIAGNOSTICS`
      (assertDictEqual, not assertIn). Counts cross-checked against upstream commit
      `0a98430` EXPECTED_ERRORS; all match except three documented divergences:
      * OCA008/027/028/029/030/031/032 also cover `_lt()` (upstream skips it due to a
        pylint-internals artifact; lazily-translated strings have the same bugs)
      * OCA009 defaults to 4 required manifest keys (upstream: license only)
      * OCA013 has no default required author (upstream: OCA) — opt-in via config
- [x] One focused positive + negative test per rule (PythonRulesTest, ManifestRulesTest)
- [x] OCA008 naming aligned: OCA008 is now genuinely translation-not-lazy
      (`_('%s' % x)` and `_('%s') % x`); f-strings moved to OCA028
      (translation-fstring-interpolation)

## 3. Repo housekeeping — DONE 2026-07-14 (except manual PyPI step)

- [x] Three stale `claude/*` remote branches deleted (verified all commits
      patch-identical to main via `git cherry` first)
- [x] Version dropped to 0.5.0 (35/63 rules)
- [ ] **Manual step**: register github.com/skysize-io/ruff-linter-odoo as a trusted
      publisher on PyPI before tagging a release. Name `ruff-linter-odoo` was still
      free on both pypi.org and test.pypi.org as of 2026-07-14.

## 4. Port the remaining rules

35 rules implemented: OCA001–OCA035. Mapping table lives in README.md
("Available Checks"). 4c decision (2026-07-14): codes stay sequential; upstream ids
are only unique with their letter prefix (C8101 ≠ E8101), so mirroring the numbers
would be ambiguous. Migration mapping is documented in the README table.

Reference implementation for everything below: `git show 0a98430:src/pylint_odoo/checkers/odoo_addons.py`
(plus `custom_logging.py`, `vim_comment.py`). Port into
`src/ruff_linter_odoo/checkers/odoo_checkers.py`; register the code, add a README table
row + upstream mapping, pin the count in EXPECTED_DIAGNOSTICS, and add focused tests.

### 4a. Manifest checks — DONE 2026-07-14
- [x] manifest-deprecated-key (C8103) → OCA015
- [x] manifest-maintainers-list (E8104) → OCA016
- [x] manifest-data-duplicated (W8125) → OCA017
- [x] manifest-behind-migrations (E8145) → OCA018
- [x] manifest-external-assets (W8162) → OCA019
- [x] missing-readme (C8112) → OCA020
- [x] website-manifest-key-not-valid-uri (W8114) → OCA021
- [x] resource-not-exist (F8101) → OCA022
- [ ] category-allowed / category-allowed-app (C8114/C8117) and the other `-app` variants
      (manifest-required-key-app C8119, missing-odoo-file C8115/C8118) — deliberately
      skipped: the Odoo app-store use case doesn't matter to us today

### 4b. Python AST checks (remaining)
- [x] translation family — DONE 2026-07-14: translation-required (C8107) → OCA023
      (raise + message_post), translation-contains-variable (W8115) → OCA024,
      translation-positional-used (W8120) → OCA025, translation-field (W8103) → OCA026,
      translation-format-interpolation (W8302) → OCA027,
      translation-fstring-interpolation (W8303) → OCA028,
      translation-format-truncated (E8301) → OCA029,
      translation-too-few/many-args (E8306/E8305) → OCA030/OCA031,
      translation-unsupported-format (E8300) → OCA032,
      prefer-env-translation (W8161) → OCA033 (gated to Odoo >= 18)
- [x] method-inverse (C8110) → OCA034, method-search (C8109) → OCA035 (2026-07-14,
      same shape as method-compute which was also reworked to upstream kwarg semantics)
- [x] Bonus fidelity fixes while porting (2026-07-14): sql-injection is now the full
      upstream port (cursor chains, +/%/format/f-string, variable assignment tracking,
      psycopg2.sql + self._table exemptions — 21/21 fixture parity); invalid-commit
      covers self._cr/self.cr/self.env.cr; method-required-super uses the full
      10-method list; odoo-addons-relative-import resolves the real module name by
      walking up to the manifest (+ Import form, migrations/tests exemptions)

Still to port (unchanged priorities):
- [ ] missing-return (W8110)
- [ ] prohibited-method-override (W8107)
- [ ] renamed-field-parameter (W8111)
- [ ] attribute-deprecated (W8105), attribute-string-redundant (W8113)
- [ ] deprecated-name-get (E8146), deprecated-odoo-model-method (W8160)
- [ ] no-write-in-compute (E8135)
- [ ] no-raise-unlink (E8140)
- [ ] except-pass (W8138)
- [ ] external-request-timeout (E8106)
- [ ] context-overridden (W8121)
- [ ] bad-builtin-groupby (W8155)
- [ ] no-search-all (W8163)
- [ ] no-wizard-in-models (C8113)
- [ ] inheritable-method-string/lambda (E8147/E8148)
- [ ] super-method-mismatch (W8164)
- [ ] test-folder-imported (E8130)
- [ ] consider-merging-classes-inherited (R8180)
- [ ] invalid-email (R8181)
- [ ] use-vim-comment (W8202)

Note: upstream also relied on pylint built-ins for some checks; anything not in the
list above that we care about (e.g. eval-used) is ruff's own job — the README now
documents that ruff-linter-odoo runs *alongside* plain ruff, not instead of it.

### 4c. Code numbering — DECIDED 2026-07-14
Sequential OCA0xx, mapping documented in the README (see rationale above and in the
odoo_checkers.py module docstring).

## 5. Feature gaps (nice-to-have, after rules)

- [x] `# noqa` support — ruff-style, tokenizer-based (comments only, not string
      literals): bare `# noqa` and `# noqa: OCA001, OCA002` (2026-07-14)
- [ ] Respect `# pylint: disable=<symbol>` comments for the ported rules — webapp-odoo
      already carries these (e.g. paas/controllers/auth.py:12); honoring them would
      make migration from pylint-odoo seamless
- [ ] Per-directory/per-file `disable` in config (config.py exists, verify granularity)
- [ ] `--output-format json` — verified wired into the CLI (`--format json|sarif|github`)
- [ ] Autofix for the mechanical rules (odoo-exception-warning, translation-not-lazy)
      — only after the rule set stabilizes

## Dogfood notes (webapp-odoo, 2026-07-14)

`ruff-linter-odoo check paas/ website_skysize/ --no-config` → 23 findings, all justified:
- 14× OCA004 (odoo.addons.paas absolute self-imports — real style issue; one site
  already carries a pylint-disable comment for it, see item 5)
- 8× OCA002 (cr.commit() in message_queue.py / res_partner.py / resources_history.py —
  deliberate per-message commits in the billing queue lanes; suppress with
  `# noqa: OCA002` if desired)
- 2× OCA023 (ValidationError with machine-readable error-code strings in auth.py —
  arguably fine untranslated)
