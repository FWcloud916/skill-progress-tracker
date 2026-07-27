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
root (configurable — see below). Works for a single-scope project or one that
spans several scopes (services, packages, sibling repos); "scope" is a
free-form label, not validated against anything.

Full spec: `references/workflow.md`
Item list: `<tracker-dir>/INDEX.md`
Template:  `<tracker-dir>/_template/PROGRESS.md`
Migration record template: `references/MIGRATION.template.md`

## Before creating anything: existing-tracker preflight

Before running `new_progress.py` or writing tracker files, inspect the target
project for existing progress-tracking artifacts and the documents that point
to them. Check likely artifacts such as root-level `PROGRESS.md`,
`progress_note/`, `progress-notes/`, `WORKLOG.md`, and any tracking path named
in `AGENTS.md`, `README.md`, or project docs. Judge by content, not filename
alone. An existing `<tracker-dir>/INDEX.md` with this skill's structure is an
already-adopted tracker, not a migration candidate.

If a separate tracking mechanism exists:

1. **Do not scaffold or mutate anything yet.** Show the user the artifacts and
   the documents/scripts that reference them.
2. **Ask whether to migrate.** An explicit answer is required; silence is not
   consent. If the user declines, preserve the existing mechanism and do not
   create a second tracker unless they explicitly choose coexistence.
3. If approved, run `migration-inventory` to produce a section-by-section
   inventory of the source (see below) **before** editing anything. Do not
   rely on an "in progress" or "current work" section alone to decide what is
   actionable — inventory the whole document. Do not invent missing facts.
   Keep the source unchanged during migration and audit.
4. Copy every actionable entry the inventory lists into the new item(s):
   current status, scope, branches/tickets/plans, goals, unfinished tasks,
   current work log, blockers, next actions, and live references. For each
   entry, fill in the record's Disposition (`migrated`, `excluded`, or
   `not-applicable`) and Destination. Every `migrated` row also needs a
   non-trivial, row-specific Evidence locator copied from the destination item; verify
   semantic equivalence against wherever it landed.
5. Update every live pointer to the old mechanism, including Markdown links,
   path mentions, agent instructions, command examples, scripts, and
   configuration.
6. Run `update_progress.py check`, search the whole project for every old path
   or filename, and inspect all changed links. Classify any remaining match as
   an intentional historical/compatibility reference. Tick the record's human
   sign-off checklist only once each item has actually been verified.
7. Run `migration-audit` — the pre-deletion gate:

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

   Only after `migration-audit` exits 0, show its output and ask whether to
   delete the original tracking artifacts. Do not infer consent. Record a
   declined deletion with `migration-finalize <slug> --decision retain`. If
   deletion is approved, run `migration-finalize <slug> --decision delete`;
   this reruns the audit, seals the exact sources and record fingerprint, and
   **does not delete anything**. Remove only those approved sources, update
   affected pointers, run pointer/link checks, then run
   `migration-finalize <slug> --confirm-deleted`.

Report the migration record's location, schema and final outcome,
`migration-audit`'s pass/fail result, the historical/reference entry counts it
disclosed, pointer files updated, and intentional legacy references.

**Migration command reference:**

```bash
# Scan the legacy source(s) and write/refresh <tracker-dir>/_migrations/<slug>.md.
# --source may repeat; a directory source is scanned recursively for *.md.
# If no tracker exists yet, this command scaffolds its support files without
# creating a progress item, so inventory still precedes destination creation.
# Re-running upgrades v1 records to v2 and preserves every compatible
# Disposition, Destination, and Evidence whose
# entry is unchanged. Sign-offs survive only an identical source + inventory;
# any inventory change resets all of them and prints that refresh result.
uv run <skill-dir>/scripts/update_progress.py migration-inventory <slug> --source <legacy-path> [--source <legacy-path>...]

# Rescan and reconcile against the record — the pre-deletion gate. Exits non-zero
# while any actionable/ambiguous entry lacks a Disposition and Destination,
# any generated field was hand-edited, any migrated Destination isn't an existing item
# slug, its Evidence is absent/non-unique, or any human sign-off box is unticked.
uv run <skill-dir>/scripts/update_progress.py migration-audit <slug>

# Persist the user's choice. The delete decision never removes files itself.
uv run <skill-dir>/scripts/update_progress.py migration-finalize <slug> --decision retain
uv run <skill-dir>/scripts/update_progress.py migration-finalize <slug> --decision delete
uv run <skill-dir>/scripts/update_progress.py migration-finalize <slug> --confirm-deleted
```

Every row in the generated record is one of five `Kind` values:
`actionable` and `ambiguous` block the audit until dispositioned; `done`,
`empty`, and `historical` are pre-filled and non-blocking. An unrecognized
heading becomes `ambiguous`, not `historical` — the scanner defaults to
blocking on what it doesn't recognize, never to treating it as already
covered.

`actionable` and `ambiguous` rows accept only `migrated` or `excluded`.
`done` and `historical` rows are seeded `not-applicable` but may instead be
`migrated` or `excluded`; `empty` rows accept only `not-applicable`. Every
historical entry is retained as its own non-blocking record row. Retaining the
whole legacy source is a durable document-level outcome after the audit, not
an entry-level `archived` disposition.

---

## Before starting work

Create the progress item with the scaffold script. Resolve `<skill-dir>` to
the directory containing this `SKILL.md`; the script can then run from
anywhere inside the project because it locates the project root itself:

```bash
# Minimal — one scope entry (branch/ticket filled in later as TBD)
uv run <skill-dir>/scripts/new_progress.py <slug> \
  --scope api \
  [--plan <path>] \
  [--title "Task title"] \
  [--dry-run]

# Full — per-scope-entry branch and ticket; --ticket is the umbrella/epic reference
uv run <skill-dir>/scripts/new_progress.py <slug> \
  --scope "api:feature/my-branch:JIRA-111,worker:feature/my-branch" \
  --ticket EPIC-100 \
  --plan <path>
```

Key arguments:
- `slug` — kebab-case identifier, e.g. `subscription-refund-flow`
- `--scope` — `name[:branch[:ticket]]`, comma-separated. `name` is a
  free-form label — not validated against any directory. Escape a literal
  comma, colon, or backslash as `\,`, `\:`, or `\\`. `branch` and
  per-entry `ticket` default to `TBD` when omitted. Ticket values are kept
  **verbatim** — this skill has no opinion on your tracker's numbering
  convention (serial, `#123`, `JIRA-111`, a URL — all pass through as given).
- `--ticket` — umbrella/epic reference for the whole task (optional, `N/A`
  if omitted). Kept verbatim.
- `--plan` — path to the associated plan file (optional but recommended when
  a plan exists). The plan is **copied** into `<tracker-dir>/_plans/` as a
  version-controlled `<slug>-<plan-name>` snapshot and linked via an explicit
  relative Markdown link in `PROGRESS.md`.
  - A path (absolute, or containing `/`) is validated by existence directly —
    works with plan output from any tool or agent.
  - A bare filename (e.g. `my-plan.md`) is resolved against
    `$PROGRESS_TRACKER_PLANS_DIR`, if that env var is set. Without it, a bare
    filename is an error asking for a path instead.
- `--title` — human-readable title (defaults to the slug title-cased)
- `--dir` — tracker directory path, relative to and strictly inside the
  project root. Nested paths and dot-directories are allowed; absolute paths,
  `.`, `..`, and symlinks that resolve outside the root are rejected. Defaults
  to `$PROGRESS_TRACKER_DIR`, then `progress`.
- `--root` — project root directory. Defaults to the current git repository's
  top level, falling back to the current working directory.

If a plan for this task exists anywhere, **always** pass it via `--plan`.

Use `--dry-run` first to preview what would be created.

On first use in a project, the script scaffolds the tracker directory's
supporting files (`README.md`, `INDEX.md`, `_template/PROGRESS.md`,
`_plans/README.md`) from this skill's bundled references — nothing to set up
by hand. An approved migration normally scaffolds those files earlier through
`migration-inventory`, before the first destination item is created.

---

## During work

Use the lifecycle script so `PROGRESS.md` and `INDEX.md` are validated and
updated together. Preview with `--dry-run` when changing status or scope:

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

The script performs these lifecycle duties:

1. **Back-fill `TBD` values** in `## Scope` as branches are created and tickets are opened
2. Tick off completed items in `## Task list` (`- [x]`)
3. Add a `### YYYY-MM-DD` entry under `## Work log` each day with brief notes
4. Update the **Updated** field to today
5. Update Status in both this `PROGRESS.md` and `<tracker-dir>/INDEX.md` per
   the lifecycle below; the two values MUST stay identical

Run an audit at any time (and before review/close-out):

```bash
uv run <skill-dir>/scripts/update_progress.py check [--dir <dir>] [--root <path>]
```

`check` detects invalid statuses, duplicate slugs/rows, missing or stale INDEX
rows, and status drift. Manual edits remain possible, but run `check`
afterward.

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

Allowed transitions are enforced by `update_progress.py`:

| From | To |
|---|---|
| `planning` | `in-progress`, `abandoned` |
| `in-progress` | `review`, `blocked`, `abandoned` |
| `review` | `in-progress`, `done`, `abandoned` |
| `blocked` | `in-progress`, `abandoned` |
| `done`, `abandoned` | None (terminal) |

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

This fills `## Outcome`, appends a final Work log entry, updates **Updated**,
and changes both status sources in one validated operation. Run `check` after
close-out.

---

## Cleanup

**Never delete current tracker items automatically.** Deleting current item
folders or removing rows from `INDEX.md` is a manual human decision. A legacy
source may be deleted only after migration audits pass and the user explicitly
confirms the exact source target. Record approval with `migration-finalize
--decision delete`, remove only its confirmed sources, then record completion
with `migration-finalize --confirm-deleted` after pointer/link checks.
