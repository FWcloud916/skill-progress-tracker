---
name: progress-tracker
description: >-
  Preflight-checked local development progress tracking under a project's
  progress/ directory. Trigger when: (1) the user starts a development task
  with a full lifecycle (investigate → fix → test → PR/MR) and wants a durable
  record — create; (2) an existing item's status, scope, or work log needs
  updating — update; (3) the tracker needs a consistency audit — audit;
  (4) finished work needs its outcome recorded — close out; (5) existing local
  tracking documents should be adopted — migrate; (6) the user invokes
  /progress-tracker. Do NOT trigger for one-off questions or trivial edits
  with no lifecycle (a typo, a config tweak); a single-scope fix with a full
  lifecycle still qualifies.
---

# Development Progress Tracker

Full spec: `references/workflow.md` · Migration contract: `references/migration.md`

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

Migration is a two-phase commit: the audit is the prepare phase; nothing is
deleted until it votes yes.

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

Create the progress item with the scaffold script — resolve `<skill-dir>` to
this `SKILL.md`'s directory; the script locates the project root itself:

```bash
uv run <skill-dir>/scripts/new_progress.py <slug> \
  --scope "api:feature/my-branch:JIRA-111,worker:feature/my-branch" \
  --ticket EPIC-100 \
  --plan <path> \
  [--title "Task title"] [--dry-run]
```

Argument semantics (slug format, per-entry defaults, `--plan` path
resolution, `--dir` containment, `--root` discovery) live in the script's
`--help` — read it before first use. Two rules the interface cannot teach at
the right moment:

- Escape a literal comma, colon, or backslash in `--scope` values as `\,`,
  `\:`, or `\\` — an unescaped comma silently splits the entry in two.
- If a plan for this task exists anywhere, **always** pass it via `--plan`.

On first use, the script scaffolds the tracker's supporting files
(`README.md`, `INDEX.md`, `_template/PROGRESS.md`, `_plans/README.md`).

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

Option semantics live in `update --help`; invalid input fails with the
allowed values. Back-fill `TBD` scope values as branches and tickets appear,
log work daily, and keep Status identical in `PROGRESS.md` and
`<tracker-dir>/INDEX.md` per the lifecycle below.

Audit consistency at any time — before review/close-out and after any manual
edit:

```bash
uv run <skill-dir>/scripts/update_progress.py check [--dir <dir>] [--root <path>]
```

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

`planning` is the scaffold default. `review` means a PR/MR is open (code
review / QA) — **not** `done`, which comes only after merge. `blocked` is
paused on an external dependency; `abandoned` is stopped without completing.

`update_progress.py` enforces exactly the transitions the diagram shows;
`done` and `abandoned` are terminal.

---

## After completing work

Close the item with the lifecycle script:

```bash
uv run <skill-dir>/scripts/update_progress.py close <slug> \
  --outcome "Merged and deployed." \
  --pr "PR #42" \
  --follow-up "Monitor error rate for one week." \
  [--status done] \
  [--dry-run]
```

Run `check` after close-out.

---

## Cleanup

**Never delete current tracker items automatically.** Deleting current item
folders or removing rows from `INDEX.md` is a manual human decision. A legacy
source may be deleted only through the migration flow's audited finalize
sequence — see `references/migration.md`.
