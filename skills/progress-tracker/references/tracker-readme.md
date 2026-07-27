# Development Progress Tracker

## Purpose

This directory is the project's **development progress tracker**: it records
progress on tasks that span one or more scopes (services, packages, repos —
whatever your project is structured around), links each task to the plan that
was active when it started, and captures the final outcome once work
completes. It is meant to be version-controlled alongside the project so
progress survives across sessions and machines. Cleanup is a manual, human
decision — nothing here is deleted automatically.

- `_plans/` — frozen snapshots of the plan that was active when each item was
  created (copied in by the scaffold script's `--plan` option). The
  `Related plan` field in each item's `PROGRESS.md` links here by relative
  path. Snapshots are immutable records of original intent; `PROGRESS.md`
  itself is the living source of truth as work progresses.

## How to add an item

**Using the scaffold script (recommended):**

Resolve `<skill-dir>` to the installed `progress-tracker` skill directory
(the directory containing its `SKILL.md`), then run:

```bash
# Minimal — one scope entry
uv run <skill-dir>/scripts/new_progress.py <slug> --scope api

# Full — per-entry branch and ticket; --ticket is the umbrella reference
uv run <skill-dir>/scripts/new_progress.py <slug> \
  --scope "api:feature/my-branch:JIRA-111,worker:feature/my-branch" \
  --ticket EPIC-100 \
  [--plan <path>] \
  [--title "Task title"] \
  [--dry-run]
```

`--scope` syntax: `name[:branch[:ticket]]`, comma-separated for multiple
entries; escape literal delimiters as `\,`, `\:`, and `\\`. Branch and ticket
default to `TBD` when omitted. The script creates
`<tracker-dir>/YYYY-MM-DD-<slug>/PROGRESS.md` and appends a row to
`INDEX.md`.

## How to update or close an item

Use the installed skill's lifecycle script so status changes are validated and
written to `PROGRESS.md` and `INDEX.md` together:

```bash
uv run <skill-dir>/scripts/update_progress.py update <slug> \
  --status in-progress \
  --work-log "Implemented validation." \
  [--scope "api:feature/task:JIRA-1"] \
  [--complete-task "Add validation"] \
  [--dry-run]

uv run <skill-dir>/scripts/update_progress.py close <slug> \
  --outcome "Merged and deployed." \
  [--pr "PR #42"] \
  [--follow-up "Monitor metrics."] \
  [--status done]

uv run <skill-dir>/scripts/update_progress.py check
```

**Manual fallback (no script):**
1. Copy `_template/PROGRESS.md` into a new folder `YYYY-MM-DD-<slug>/`
2. Replace every `{{PLACEHOLDER}}`
3. Add a row to the [`INDEX.md`](INDEX.md) table manually

Invoke the installed `progress-tracker` skill for the full workflow and
allowed status transitions. Item list: [`INDEX.md`](INDEX.md).

## Migrating an existing tracking mechanism

If this project already has a separate tracker (a root `PROGRESS.md`,
`WORKLOG.md`, etc.), do not copy its content by hand. Migration is
script-gated so an empty "in progress" section can never be mistaken for an
empty actionable set:

```bash
uv run <skill-dir>/scripts/update_progress.py migration-inventory <slug> --source <legacy-path>
uv run <skill-dir>/scripts/update_progress.py migration-audit <slug>
uv run <skill-dir>/scripts/update_progress.py migration-finalize <slug> --decision retain|delete
```

`migration-inventory` scans the legacy source whole-document and writes a
reconciliation record to `_migrations/<slug>.md`. On first adoption it can
scaffold this tracker before any destination item exists; `migration-audit` is the
pre-deletion gate — it fails while any actionable/ambiguous entry lacks a
valid `migrated` or `excluded` disposition and destination, any generated
record field changed, migrated Evidence is absent/non-unique, or a required
sign-off is incomplete. `migration-finalize` records the user's durable
outcome and never deletes a source. Invoke the
installed `progress-tracker` skill for the full contract.

## Cleanup policy

Tools and AI agents **do not** delete item folders automatically. Cleanup
(deleting folders, removing INDEX rows) is a **manual, human decision**, done
as needed. A migrated legacy source may be deleted only after
`migration-audit` exits 0 and `migration-finalize --decision delete` seals
the exact sources. Record completion afterward with `--confirm-deleted`.
