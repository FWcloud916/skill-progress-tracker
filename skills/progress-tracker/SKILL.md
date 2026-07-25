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

> If you're inside Kdan Mobile's `kdan-workflow` workspace, use the
> workspace-specific `progress-note` skill instead — it wires into that
> workspace's ticket system and multi-service layout. This skill is the
> generic, workspace-independent sibling for any other project.

---

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
3. If approved, agree on a source-to-destination map before editing. Copy all
   **in-progress content** into the new item(s): current status, scope,
   branches/tickets/plans, goals, unfinished tasks, current work log, blockers,
   next actions, and live references. Do not invent missing facts. Keep the
   source unchanged during migration and audit.
4. Audit source and destination side by side. For every active source field,
   record its destination and verify semantic equivalence; explicitly document
   any mapping into this skill's canonical status or field structure. A
   migration with missing or unexplained active content fails.
5. Update every live pointer to the old mechanism, including Markdown links,
   path mentions, agent instructions, command examples, scripts, and
   configuration.
6. Run `update_progress.py check`, search the whole project for every old path
   or filename, and inspect all changed links. Migration is complete only when
   the content comparison and pointer audit both pass, every remaining match is
   an intentional historical/compatibility reference, and every changed
   relative link resolves.
7. Only after that clean audit, show the results and ask whether to delete the
   original tracking artifacts. Do not infer consent. If deletion is approved,
   remove only the confirmed legacy targets, update any resulting pointers,
   then rerun the consistency, old-reference, and link audits. If declined,
   retain the originals as legacy records and keep live pointers on the new
   tracker.

Report the active-content mapping, two-sided consistency result, pointer files
updated, intentional legacy references, and the user's source-retention choice.
Use a comparison table with `Source artifact/field`, `Source value summary`,
`Destination item/section`, and `Result`; every row MUST pass before asking
about deletion.

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
by hand.

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
confirms the exact source target; rerun all audits afterward.
