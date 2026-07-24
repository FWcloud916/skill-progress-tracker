# Progress Tracker Improvement Plan

## Objective

Turn the current creation-focused skill into a dependable full-lifecycle
tracker while preserving its existing project-agnostic design, CLI
compatibility, and safety boundaries.

## Guiding principles

- Enhance the existing workflow instead of replacing it.
- Keep deterministic behavior in scripts and cover it with deterministic tests.
- Preserve verbatim ticket semantics and free-form scope labels.
- Keep all tracker writes contained inside the selected project root.
- Keep `PROGRESS.md` as the living task record and plan snapshots immutable.

## Workstreams

### 1. Close the lifecycle automation gap

- Add a script-supported update path for status, Updated date, work-log entries,
  task completion, and scope back-filling.
- Add a close-out path for Outcome, final status, and PR/commit references.
- Update `PROGRESS.md` and its `INDEX.md` row as one validated operation.
- Enforce the canonical status enum and allowed transitions.
- Add an audit/check mode that detects missing items, duplicate rows, stale
  INDEX links, invalid statuses, and status drift.

Acceptance criteria:

- Normal create, update, review, blocked/resume, done, and abandoned flows no
  longer require hand-editing status in two files.
- Invalid transitions and ambiguous item matches fail before writing.
- Dry-run output shows every proposed file change.

### 2. Harden structured input and Markdown rendering

- Define how commas and colons are represented in scope labels, or introduce a
  repeatable structured scope argument while retaining the current syntax.
- Escape or reject Markdown table delimiters, backticks, and embedded newlines
  in title, scope, branch, ticket, and plan display values.
- Add regression tests for URLs, pipes, Unicode, whitespace, commas, colons,
  backticks, and multiline input.

Acceptance criteria:

- Every accepted input produces valid Markdown tables.
- The documentation no longer promises unrestricted free-form values beyond
  what the CLI can encode.
- Existing documented CLI examples remain compatible.

### 3. Make verification claims true

- Run all lifecycle scenarios from `scripts/verify.sh`, not only the scenario
  grader's unit tests.
- Fail the verification gate when neither uv nor pytest is available instead
  of reporting a successful skip.
- Keep Ruff pinned to the exact CI version and verify documentation accurately
  describes which checks run locally and in CI.

Acceptance criteria:

- A successful `bash scripts/verify.sh` proves pytest, grader regression tests,
  and all lifecycle scenarios passed.
- CI and `evals/README.md` describe the same executed checks.

### 4. Improve runtime and plan-snapshot portability

- Determine the real minimum supported Python version from used language and
  stdlib features, then test and lower `requires-python` where safe.
- Add CI coverage for the minimum and current supported Python versions.
- Namespace plan snapshots by task slug or item identity so common filenames
  such as `plan.md` can be reused without overwriting immutable snapshots.
- Render plan references as explicit relative Markdown links.

Acceptance criteria:

- The scaffold runs on the documented minimum Python version.
- Two tasks can snapshot different files with the same basename safely.
- Existing snapshots and existing tracker directories remain readable.

### 5. Synchronize documentation, evals, and packaging

- Update SKILL.md, workflow references, templates, README, design decisions,
  CLI help, tests, and affected scenarios in the same changes.
- Add trigger/eval coverage if the new update, audit, or close-out language
  changes the skill's activation boundary.
- Bump the Claude plugin version for user-visible behavior changes.

## Suggested delivery order

1. Verification truthfulness and missing edge-case tests.
2. Markdown/input hardening with backward-compatible parsing.
3. Lifecycle update, close-out, and audit automation.
4. Python compatibility and plan snapshot naming improvements.
5. Documentation sync, full verification, and plugin release bump.

## Non-goals

- Integrating a specific issue tracker or hosting provider.
- Automatically deleting completed or abandoned tracker items.
- Replacing local Markdown records with a database or hosted service.
- Rewriting the existing creation command without a compatibility path.

## Final verification

- `bash scripts/verify.sh`
- `uv run --with pytest python3 -m pytest skills/progress-tracker/scripts/ -v`
- `python3 evals/scripts/run_scenarios.py`
- `python3 evals/scripts/test_grade_scenarios.py`
- `uvx ruff==0.16.0 check .`
