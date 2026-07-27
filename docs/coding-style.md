# progress-tracker — Coding Style Guide

> **Type:** Reference / How-to
> **Audience:** Developers, AI assistants, code reviewers
> **Last updated:** 2026-07-27
>
> This document describes the coding style conventions for progress-tracker. It covers both **linter-enforced rules** and **repository contracts** that cannot be auto-checked by Ruff.
>
> Configuration sources: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), [`scripts/verify.sh`](../scripts/verify.sh), inline `noqa` annotations, and [`AGENTS.md`](../AGENTS.md).
>
> **Terminology:** This document uses RFC 2119 keywords — **MUST** (mandatory), **SHOULD** (recommended), **MAY** (optional).

---

## 1. Linter Overview

Python files are linted with Ruff 0.16.0. The version is pinned in
`.github/workflows/ci.yml` because an older local Ruff once passed code that the newer CI
version rejected. Maintainer linting therefore uses the exact pinned version rather than
a `ruff` executable already present on `PATH`.

The repository has no `pyproject.toml`, `ruff.toml`, or `.ruff.toml`. Consequently:

- there is no repository-configured rule selection, line length, target Python version,
  per-file ignore table, or excluded-path list;
- Ruff runs with the behavior of the pinned 0.16.0 release and the command-line options
  shown in §6; and
- rule suppressions are local inline annotations and require an explanation where the
  reason is not self-evident.

Python 3.14 is the project runtime floor, but that constraint comes from both scripts'
PEP 723 metadata plus CI and verification checks, not from Ruff configuration.

## 2. Linter Rules Summary

Because there is no Ruff configuration file, this section records only observable,
project-controlled behavior—not an inferred list of Ruff defaults.

| Rule or setting | Repository behavior | Source |
|---|---|---|
| Ruff version | MUST be exactly `0.16.0` | `.github/workflows/ci.yml`; `AGENTS.md` hard constraint |
| Invocation | Check the repository with `check .` | CI lint step and maintainer command |
| Explicit rule selection | None | No Ruff config or CLI `--select`/`--ignore` |
| Explicit exclusions | None | No Ruff config or CLI `--exclude` |
| Local calendar dates | `DTZ011` is suppressed on intentional `date.today()` calls | Inline `# noqa: DTZ011` in lifecycle code and date assertions |
| Automatic fixes/formatting | Not part of the repository gate | CI and `AGENTS.md` specify check-only commands |

The local-date suppression is a domain decision: folder and work-log dates represent
the developer's calendar day. It SHOULD remain attached to the smallest expression and
MUST NOT become a broad file-level ignore.

## 3. Project-Specific Code Examples

### 3.1 PEP 723 executable scripts

Both public CLIs are standalone files with the same runtime declaration and no
third-party runtime dependencies:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
```

Sources: `skills/progress-tracker/scripts/new_progress.py` and
`skills/progress-tracker/scripts/update_progress.py`. A Python-version change MUST update
both headers, CI, and the checks in `scripts/verify.sh` together.

### 3.2 Deferred annotations across Python modules

Production scripts, pytest files, and evaluation scripts consistently place
`from __future__ import annotations` immediately after the module docstring. New Python
modules SHOULD follow this pattern so modern type syntax remains safe during dynamic
module loading and test collection.

### 3.3 Explicit subprocess behavior

Subprocess calls use argument arrays and state whether failure is exceptional:

```python
out = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"],
    capture_output=True,
    text=True,
    check=True,
)
```

CLI tests and scenario execution instead use `check=False` so they can assert expected
non-zero exits. New subprocess calls MUST choose `check=True` or `check=False`
explicitly and MUST NOT build a shell command from user-controlled text.

### 3.4 Structured migration records

`update_progress.py` uses dataclasses (`Section`, `RawEntry`, `SourceEntry`,
`RecordRow`, `MigrationOutcome`, and `MigrationRecord`) once a parsed record has multiple
named fields. Similar parsed domain structures SHOULD use typed dataclasses instead of
position-dependent dictionaries or tuples. Compact shared values such as the three-part
`ScopeEntry` MAY remain a documented type alias.

## 4. Team Conventions (Not Enforced by the Linter)

### 4.1 Behavior and tests change together

Changes to `new_progress.py` MUST include matching coverage in
`test_new_progress.py`. Changes to lifecycle, audit, scanner, reconciliation, or
finalization behavior in `update_progress.py` MUST include matching coverage in
`test_update_progress.py`.

Good:

```text
update_progress.py: reject reused migration Evidence
test_update_progress.py: prove two rows cannot share one locator
```

Bad:

```text
Change a CLI branch and rely only on a manual invocation.
```

When a CLI flag, output file, or file-scope behavior changes, the matching
`evals/scenarios/*/scenario.json` contract and grader assertions MUST change in the same
work item.

### 4.2 Mirrored constants are contracts

Template placeholders, exact table headers, marker comments, migration sign-off labels,
disposition values, and the canonical status block are intentionally duplicated across
code and documentation. A contributor MUST update every protected copy together and run
`scripts/verify.sh`.

Good:

```text
Add a migration placeholder to MIGRATION.template.md, its renderer, and verify coverage.
```

Bad:

```text
Rename a Markdown table header without updating the parser's exact marker constant.
```

The authoritative protected sets and file lists are documented in `AGENTS.md`; do not
guess them from nearby naming alone.

### 4.3 Validate before writing

Mutating commands SHOULD build and validate prospective state before their first write.
Path containment, source/template existence, collision detection, Markdown rendering,
and index parsing belong in preflight logic.

Good:

```python
rendered = render_template(...)
updated_index, new_row = render_index_update(...)
scaffold_tracker_dir(tracker_dir, dry_run)
```

Bad:

```python
item_dir.mkdir(parents=True)
# Later discover that INDEX.md has no insertion marker.
```

When a multi-file mutation cannot be transactional, the implementation MUST state its
guarantee honestly. `write_validated_pair()` provides best-effort rollback for ordinary
write errors, not crash-safe atomicity.

### 4.4 Fail closed at safety boundaries

Ambiguous migration content, missing evidence, stale generated fields, path escapes,
and inconsistent status sources MUST block the operation. Unknown input MUST NOT be
silently interpreted as already migrated, historical, or safe to delete.

Good:

```python
return "ambiguous"  # unrecognized heading; blocks reconciliation
```

Bad:

```python
return "historical"  # suppresses review of an unknown section
```

### 4.5 Preserve user semantics

Ticket references MUST remain verbatim apart from trimming and empty defaults. Scope
names MUST remain free-form labels rather than filesystem lookups. Bare plan filenames
MUST resolve only through `$PROGRESS_TRACKER_PLANS_DIR`; do not add a tool-specific
implicit plan directory.

Good:

```python
return value.strip() if value.strip() else default
```

Bad:

```python
return f"#{value}" if value.isdigit() else value
```

### 4.6 Use actionable CLI errors

Input and state validation errors use `sys.exit("ERROR: ...")` with the rejected value
or expected corrective action. Read-only audits accumulate independent failures and
print all of them before returning non-zero. New validation SHOULD preserve this split:
fail immediately when safe continuation is impossible; aggregate when the command's job
is diagnosis.

## 5. Architecture Conventions

The component flow is described in [project-overview.md §3](project-overview.md#3-architecture-overview).
The following boundaries apply when changing code:

- `new_progress.py` owns shared parsing, Markdown rendering, project-root containment,
  and tracker scaffolding. `update_progress.py` MAY import those helpers; the creation
  script MUST NOT import the lifecycle script.
- Bundled seed content belongs under `skills/progress-tracker/references/`. Python code
  reads and fills it; it SHOULD NOT embed a second full copy of a template.
- `new_progress.py` owns creation only. Existing-item update, close-out, consistency
  audit, migration inventory, reconciliation, and finalization belong in
  `update_progress.py`.
- Runtime code MUST remain tracker-agnostic: no repository-name assumptions, fixed
  workspace root, ticket-system normalization, or network client integration.
- Current-item cleanup stays outside automated scripts. Migration finalization MAY
  verify a user-approved removal but MUST NOT perform deletion.
- Plugin packaging MUST point at the canonical `skills/progress-tracker/` payload rather
  than introducing a generated plugin copy.

## 6. Running the Linter (Pre-Merge)

Run the exact maintainer command from `AGENTS.md`:

```bash
uvx ruff==0.16.0 check .
```

CI provisions and invokes the same pinned release through two commands:

```bash
uv tool install ruff==0.16.0
uv tool run ruff check .
```

The repository does not define a changed-files-only lint command. Do not substitute a
locally installed unpinned `ruff` binary as evidence that CI will pass.

Lint is only one part of completion. The mandatory repository gate is:

```bash
bash scripts/verify.sh
```

That script checks cross-file contracts and runs pytest plus end-to-end scenarios that
Ruff cannot validate.

## 7. References

- [`AGENTS.md`](../AGENTS.md) — task routing, hard constraints, and exact verification
  commands.
- [project-overview.md](project-overview.md) — architecture, CLI surfaces, directory
  layout, and delivery pipeline.
- [domain-models.md](domain-models.md) — record shapes, lifecycle, reconciliation, and
  filesystem safety mechanisms.
- [`docs/design-decisions.md`](design-decisions.md) — rationale and incident history
  behind runtime, lint, migration, and packaging choices.
- [`evals/README.md`](../evals/README.md) — deterministic scenario and trigger-boundary
  contracts.
