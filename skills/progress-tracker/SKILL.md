---
name: progress-tracker
description: >-
  Manages local development progress tracking under a project's progress/
  directory. Trigger this skill when: (1) the user wants to start tracking a
  development task that runs a full lifecycle (investigate → fix → test →
  PR/MR), whether it touches one scope (service, package, repo) or spans
  several — and wants a progress record; (2) the user asks to create,
  update, audit/check, close out, or migrate a progress item or existing local
  tracking documents; (3) the user explicitly invokes /progress-tracker. Do
  NOT trigger for genuine one-off questions or trivial
  edits with no lifecycle to track (a typo fix, a config tweak, answering a
  question) — a single-scope bug fix that goes through investigate/fix/test/PR
  still qualifies for (1).
---

# Development Progress Tracker

Track development tasks locally under a `progress/` directory at the project
root (configurable). A task may span one scope or several (services, packages,
sibling repos).

Full spec: `references/workflow.md`
Migration contract: `references/migration.md`

## Before creating anything: existing-tracker preflight

Before running `new_progress.py` or writing tracker files, inspect the target
project for existing progress-tracking artifacts and the documents that point
to them. Check likely artifacts such as root-level `PROGRESS.md`,
`progress_note/`, `progress-notes/`, `WORKLOG.md`, and any tracking path named
in `AGENTS.md`, `README.md`, or project docs. Judge by content, not filename
alone. An existing `<tracker-dir>/INDEX.md` with this skill's structure is an
already-adopted tracker, not a migration candidate.

A separate tracking mechanism exists → show the user the artifacts and the
documents that reference them, then ask whether to migrate. An explicit answer
is required; silence is not consent. A declined migration preserves the
existing mechanism; a second tracker requires an explicit coexistence choice.

A migration was approved → read `references/migration.md` in full before
running any migration command.

<!-- MIGRATION_GATE_START -->
Migration is script-gated. The deletion question MUST NOT be asked until both
commands have run and the second exited 0:

```bash
uv run <skill-dir>/scripts/update_progress.py migration-inventory <slug> --source <legacy-path>
uv run <skill-dir>/scripts/update_progress.py migration-audit <slug>
```

`migration-audit` fails while any actionable or ambiguous source entry lacks a
valid `migrated` or `excluded` disposition and destination, or any `migrated`
row lacks Evidence that occurs exactly once in its destination item. Its human
sign-offs cover work already performed. An empty WIP section is not evidence
of an empty actionable set.
<!-- MIGRATION_GATE_END -->

---

## Before starting work

Create the progress item with the scaffold script. Resolve `<skill-dir>` to
the directory containing this `SKILL.md`; the script locates the project root
itself, so it runs from anywhere inside the project:

```bash
uv run <skill-dir>/scripts/new_progress.py <slug> \
  --scope "api:feature/my-branch:JIRA-111,worker:feature/my-branch" \
  --ticket EPIC-100 \
  --plan <path> \
  [--title "Task title"] [--dry-run]
```

Key arguments:
- `slug` — kebab-case identifier, e.g. `subscription-refund-flow`
- `--scope` — `name[:branch[:ticket]]`, comma-separated. `name` is a
  free-form label — not validated against any directory. Escape a literal
  comma, colon, or backslash as `\,`, `\:`, or `\\`. `branch` and per-entry
  `ticket` default to `TBD` when omitted. Ticket values are kept **verbatim**
  — any numbering convention passes through as given.
- `--ticket` — umbrella/epic reference for the whole task (optional, `N/A`
  if omitted). Kept verbatim.
- `--plan` — path to the associated plan file. The plan is **copied** into
  `<tracker-dir>/_plans/` as a version-controlled `<slug>-<plan-name>`
  snapshot and linked via a relative Markdown link in `PROGRESS.md`. A path
  (absolute, or containing `/`) is validated by existence directly; a bare
  filename resolves against `$PROGRESS_TRACKER_PLANS_DIR` and is an error
  when that env var is unset.
- `--title` — human-readable title (defaults to the slug title-cased)
- `--dir` — tracker directory path, relative to and strictly inside the
  project root; absolute paths, `.`, `..`, and symlinks that resolve outside
  the root are rejected. Defaults to `$PROGRESS_TRACKER_DIR`, then `progress`.
- `--root` — project root. Defaults to the git toplevel, then the cwd.

If a plan for this task exists anywhere, **always** pass it via `--plan`.

On first use in a project, the script scaffolds the tracker directory's
supporting files (`README.md`, `INDEX.md`, `_template/PROGRESS.md`,
`_plans/README.md`) from this skill's bundled references.

---

## During work

Use the lifecycle script so `PROGRESS.md` and `INDEX.md` are validated and
updated together:

```bash
uv run <skill-dir>/scripts/update_progress.py update <slug> \
  --status in-progress \
  --scope "api:feature/my-branch:JIRA-111" \
  --work-log "Implemented request validation." \
  --complete-task "Add request validation" \
  [--dry-run]
```

All update options are optional individually, but at least one is required.
`--complete-task` may be repeated and matches the exact text of an unchecked
Task list entry. `--scope` replaces the full Scope table using the same escaped
syntax as `new_progress.py`.

In one validated operation it back-fills `TBD` scope values as branches and
tickets appear, ticks completed Task list items, adds the dated `## Work log`
entry, bumps **Updated**, and keeps Status identical in `PROGRESS.md` and
`<tracker-dir>/INDEX.md` per the lifecycle below.

Run an audit at any time (and before review/close-out):

```bash
uv run <skill-dir>/scripts/update_progress.py check [--dir <dir>] [--root <path>]
```

`check` detects invalid statuses, duplicate slugs/rows, missing or stale INDEX
rows, and status drift; run it after any manual edit.

---

## Status lifecycle (canonical)

The Status fields in `PROGRESS.md` and `<tracker-dir>/INDEX.md` take exactly
these values and MUST stay identical:

<!-- STATUS_LIFECYCLE_START -->
Status enum: `planning`, `in-progress`, `review`, `blocked`, `done`, `abandoned`

```
planning → in-progress ⇄ review → done
                ↕
             blocked

Any non-terminal status → abandoned
```
<!-- STATUS_LIFECYCLE_END -->

| Status | Meaning |
|---|---|
| `planning` | Item created, implementation not started (scaffold-script default) |
| `in-progress` | Under active development |
| `review` | PR/MR opened, in code review / QA — **not** `done`; that comes after merge |
| `blocked` | Paused on an external dependency |
| `done` | Development complete (PR/MR merged) |
| `abandoned` | Stopped without completing |

`update_progress.py` enforces exactly the transitions the diagram shows;
`done` and `abandoned` are terminal.

---

## After completing work

Close the item with the lifecycle script. `--outcome` is required; `--status`
defaults to `done` and may also be `abandoned`:

```bash
uv run <skill-dir>/scripts/update_progress.py close <slug> \
  --outcome "Merged and deployed." \
  --pr "PR #42" \
  --follow-up "Monitor error rate for one week." \
  [--status done] \
  [--dry-run]
```

This fills `## Outcome`, appends a final Work log entry, and changes both
status sources in one validated operation. Run `check` after close-out.

---

## Cleanup

**Never delete current tracker items automatically.** Deleting current item
folders or removing rows from `INDEX.md` is a manual human decision. A legacy
source may be deleted only through the migration flow's audited finalize
sequence — see `references/migration.md`.
