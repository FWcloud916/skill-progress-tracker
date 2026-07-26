# Progress tracking workflow

> **Type:** How-to
> **Audience:** Developers, AI assistants
> **Last updated:** 2026-07-26
>
> This document explains the **workflow and purpose** of the progress tracker
> (why, folder structure, field semantics, cleanup policy). The single
> source of truth for **operating mechanics** (script argument spec, `--plan`
> resolution rules, status enum) is [`../SKILL.md`](../SKILL.md).
>
> **Terminology:** this document uses RFC 2119 keywords — **MUST**,
> **SHOULD**, **MAY**.

---

## Purpose

Provide a **unified, local progress-tracking mechanism** so developers (and AI
agents) always know, during development:
- Which tasks are in flight (especially tasks spanning more than one scope)
- How each task relates to the plan that existed before development started
- The final outcome once development finishes

The tracker directory (`progress/` by default) lives at the project root and
is version-controlled alongside the project, so progress records survive
across sessions and machines.

---

## Prerequisites

- **uv** (recommended): `uv run` installs Python automatically and reads the
  PEP 723 inline metadata, no manual pip needed.
- Or: Python 3.14+ (pure stdlib, no third-party dependencies), run directly
  with `python3 new_progress.py`.

---

## Existing-tracker discovery and migration

Before first use, the agent **MUST** inspect the project for an existing local
tracking mechanism and for project documents, agent instructions, scripts, or
configuration that point to it. Likely names include root-level `PROGRESS.md`,
`progress_note/`, `progress-notes/`, and `WORKLOG.md`, but content and documented
purpose determine whether an artifact is a tracker. A tracker already using
this skill's `<tracker-dir>/INDEX.md` structure is not a migration candidate.

When a separate mechanism exists, the agent **MUST NOT** scaffold a parallel
tracker without first showing the discovered artifacts and asking whether the
user wants to migrate. Migration requires explicit approval. A declined
migration preserves the existing mechanism; coexistence also requires an
explicit user choice.

An approved migration follows this contract. It is **script-gated**, not a
judgment call: a real migration trial once treated an empty "current work"
section as proof a legacy source held no actionable content, while a
"Next steps" section and a backlog it never inspected still held unmigrated
work (see `KNOWN-ISSUE.md` KI-001 in the repository root for the incident this
contract was hardened against). `migration-inventory` and `migration-audit`
exist specifically so that judgment call is no longer load-bearing.

1. Inventory source artifacts and all live pointers to them. Run
   `migration-inventory <slug> --source <legacy-path>` to produce a
   section-by-section inventory record at `<tracker-dir>/_migrations/<slug>.md`
   — this scans the **whole document**, not just an "in progress" or "current
   work" section, and defaults every unrecognized heading to `ambiguous`
   (blocking) rather than assuming it is safe to ignore.
2. Agree on a source-to-destination mapping; do not infer missing task facts.
3. Keep the source unchanged and copy every in-progress concern into the new
   item(s): current status, scope, branch/ticket/plan references, goals,
   unfinished tasks, current work log, blockers, next actions, and live links.
   For each `actionable`/`ambiguous` row in the inventory record, fill in its
   Disposition (`migrated`, `excluded`, `archived`, or `not-applicable`) and
   Destination.
4. Compare source and destination field by field. For each `migrated` row,
   verify semantic equivalence with wherever it landed and tick the record's
   corresponding sign-off box. Missing or unexplained active content — any
   row still `TBD` — fails the audit.
5. Update every live pointer: links, path mentions, agent instructions, command
   examples, scripts, and configuration.
6. Run `update_progress.py check`, search the project for each old path/name,
   and verify every changed relative link resolves. Classify any remaining
   match as an intentional historical/compatibility reference, then tick the
   record's remaining sign-off boxes (historical sections disclosed, pointer
   audit passed, link audit passed).
7. Run `migration-audit <slug>` — the deletion gate:

<!-- MIGRATION_GATE_START -->
Migration is script-gated. The deletion question MUST NOT be asked until both
commands have run and the second exited 0:

```bash
uv run <skill-dir>/scripts/update_progress.py migration-inventory <slug> --source <legacy-path>
uv run <skill-dir>/scripts/update_progress.py migration-audit <slug>
```

`migration-audit` fails while any actionable or ambiguous source entry lacks a
disposition and destination. An empty WIP section is not evidence of an empty
actionable set.
<!-- MIGRATION_GATE_END -->

   Only once `migration-audit` exits 0, show its output and ask whether to
   delete the original artifacts. If approved, remove only the exact confirmed
   legacy targets, update affected pointers, and rerun `migration-audit`,
   `update_progress.py check`, and the old-reference/link audits. If declined,
   retain the originals as legacy records while live pointers continue to
   target the new tracker.

The migration is not complete while `migration-audit` exits non-zero, active
content is missing, the two records disagree, or an unreviewed stale pointer
remains. The final report lists the migration record's location,
`migration-audit`'s result, the historical/reference sections it disclosed,
updated pointer files, intentional legacy references, and source-retention
choice.

---

## Quick usage

### 1. Before starting work: create the item

Run `new_progress.py <slug> --scope … [--ticket …] [--plan …] [--title …]
[--dir …] [--root …] [--dry-run]`. Full argument spec (`--scope`
`name[:branch[:ticket]]` syntax, `--plan` resolution rules) →
[`SKILL.md`](../SKILL.md) §Before starting work.

The script will:
1. Scaffold the tracker directory's supporting files on first use
   (`README.md`, `INDEX.md`, `_template/PROGRESS.md`, `_plans/README.md`)
2. Create `<tracker-dir>/YYYY-MM-DD-<slug>/PROGRESS.md`, filling in every
   field from `_template/PROGRESS.md` and expanding the `## Scope` table
3. Append a row (status `planning`) to `<tracker-dir>/INDEX.md`

### 2. During work: keep the record current

Run `update_progress.py update <slug>` with `--status`, `--scope`,
`--work-log`, and/or repeatable `--complete-task` options. The script updates
the living record and its INDEX status together after validating current
consistency and the requested transition. Field-by-field spec and the status enum
(`planning` / `in-progress` / `review` / `blocked` / `done` / `abandoned`) →
[`SKILL.md`](../SKILL.md) §During work, §Status lifecycle.

### 3. After work: close out

Run `update_progress.py close <slug> --outcome <text>` with optional `--pr`,
`--follow-up`, and `--status done|abandoned`. The script fills `## Outcome`,
adds a final Work log entry, updates **Updated**, and synchronizes the two
status fields. Run `update_progress.py check` to audit the result.

### Manual fallback (no script)

1. Copy `_template/PROGRESS.md` into a new folder `<tracker-dir>/YYYY-MM-DD-<slug>/`
2. Replace every `{{PLACEHOLDER}}` (`{{TITLE}}`, `{{SLUG}}`, `{{SCOPE_ROWS}}`,
   `{{TICKET}}`, `{{PLAN}}`, `{{DATE}}`); `{{SCOPE_ROWS}}` expands to one row
   per scope entry in `## Scope`
3. Add a row to the `INDEX.md` table manually

---

## Folder structure

```
progress/
├── README.md                          # purpose / how-to / cleanup policy (stable doc)
├── INDEX.md                           # item list (single list, human + tool maintained)
├── _template/
│   └── PROGRESS.md                    # single source of truth for the template (script fills this in)
├── _plans/                            # version-controlled frozen plan snapshots (script's --plan copies here)
│   ├── README.md
│   └── subscription-refund-refund-flow-abstract-breeze.md
├── _migrations/                       # only present once a migration-inventory has run
│   ├── README.md
│   └── legacy-progress-md.md          # inventory + reconciliation record; the deletion gate
├── 2026-06-17-subscription-refund/    # one development task (date prefix + kebab-case slug)
│   └── PROGRESS.md                    # that task's progress record
└── 2026-06-20-receipt-sync-fix/
    └── PROGRESS.md
```

**Naming convention:** `YYYY-MM-DD-<slug>/`
- `slug` MUST be kebab-case (lowercase letters, digits, hyphens), e.g. `subscription-refund-flow`
- The date prefix keeps folders sorted chronologically
- The script refuses to overwrite an existing folder (idempotency guard)

---

## PROGRESS.md field reference

### Task-level (metadata block)

| Field | Meaning |
|---|---|
| **Slug** | The kebab-case identifier used in the folder name — a stable, machine-readable ID distinct from the human-readable title |
| **Status** | Current progress; see the status section below |
| **Ticket** | Umbrella/epic reference for the whole task; kept verbatim; `N/A` if none |
| **Related plan** | Explicit relative Markdown link to the slug-namespaced version-controlled snapshot (`../_plans/<slug>-<name>`), or `N/A`. The snapshot is copied in by the script at creation time and is a frozen record of original intent; `PROGRESS.md` itself is the living source of truth as development proceeds. |
| **Created** | `YYYY-MM-DD`, filled in automatically by the script |
| **Updated** | Updated by hand or by an agent every time the record changes |

### Scope-level (`## Scope` table)

One row per scope entry, filled in progressively during development:

| Field | Meaning |
|---|---|
| **Scope** | A free-form label for the piece of work, e.g. `api`, `payments-service`, `mobile-app` |
| **Branch** | The development branch for this scope entry, e.g. `feature/subscription-refund`; `TBD` before it exists |
| **Ticket** | This scope entry's ticket/issue reference, kept verbatim; `TBD` before one is opened |
| **Notes** | Any per-scope-entry supplementary notes |

### Other sections

| Field | Meaning |
|---|---|
| **Background & goals** | Task background, motivation, expected outcome |
| **Task list** | `- [ ]` checkboxes, ticked off during development |
| **Work log** | Dated `### YYYY-MM-DD` entries, accumulated over time |
| **Outcome** | Filled in after development ends: final status, PR/commit refs, follow-ups |

---

## Status lifecycle

Keep the status values in `PROGRESS.md` and `INDEX.md` identical at every
transition. This block is mirrored exactly in [`SKILL.md`](../SKILL.md) and
the scaffolded `INDEX.md`:

<!-- STATUS_LIFECYCLE_START -->
Status enum: `planning`, `in-progress`, `review`, `blocked`, `done`, `abandoned`

```
planning → in-progress ⇄ review → done
                ↕
             blocked

Any non-terminal status → abandoned
```
<!-- STATUS_LIFECYCLE_END -->

---

## Relationship to plans

`_plans/` is a version-controlled subdirectory of the tracker that holds a
**frozen snapshot** of the plan active when each task was created. The
script's `--plan` option copies the plan file in from wherever it was
originally written, so the snapshot travels with the repository regardless of
machine. Resolution rules for bare filenames vs. paths →
[`SKILL.md`](../SKILL.md) §Before starting work.

The script copies the plan to `_plans/<slug>-<name>.md`; `PROGRESS.md`'s
**Related plan** field records an explicit relative Markdown link. Prefixing
the task slug preserves immutable snapshots while allowing different tasks to
reuse common source filenames such as `plan.md`.

**Why copy instead of writing directly into `_plans/`?** Different planning
tools and agents write their plan output to different locations, and some of
those locations aren't configurable. Copying is the one mechanism that
converges every source into version control.

**Positioning:** the `_plans/` snapshot is the **original intent** at the
moment the task was created and is never modified afterward. `PROGRESS.md`
itself is the **single source of truth** that keeps evolving during
development; the plan's key points should keep getting distilled into its
sections. A missing snapshot (switched machines, plan cleaned up) doesn't
block picking the work back up, because `PROGRESS.md` is self-sufficient on
its own.

---

## Cleanup policy

- Scripts and AI agents **MUST NOT** proactively delete current item folders or
  INDEX rows.
- A migrated legacy source MAY be deleted only after `migration-audit` exits 0
  and the user explicitly confirms the exact target. The agent MUST rerun
  `migration-audit`, `update_progress.py check`, and the pointer/link audits
  after deletion.
- Do not delete a `<tracker-dir>/_migrations/<slug>.md` record while its
  legacy source still exists — it is the audit trail proving the migration
  was complete.
- Other cleanup remains a **human decision**, performed manually as needed.
- Consider keeping `done` / `abandoned` items around for at least one sprint
  for later reference and retrospectives.

---

## ✅ Do / ❌ Don't

✅ **Do**

- Discover existing tracking artifacts and ask before migrating or scaffolding
  a parallel tracker
- Run `migration-inventory` before copying anything — inventory the whole
  source document, not just an "in progress" or "current work" section
- Dispose of every `actionable`/`ambiguous` inventory row and run
  `migration-audit` before asking whether to delete the source
- Audit every old path/name and changed link after an approved migration
- Preview with `--dry-run` before creating a task
- Include **every scope entry involved** in `--scope`, even read-only ones
- Fill in `TBD` for branch/ticket before they exist, then back-fill `## Scope` once known
- Always link a plan-mode/planning-tool plan via `--plan` when one exists
- Escape literal scope delimiters as `\,`, `\:`, and `\\`
- Pass an umbrella/epic reference via `--ticket` when one exists; it's kept exactly as given
- Use `update_progress.py update` / `close` for lifecycle mutations, then run `check`
- Update `## Work log` daily, at a granularity that supports retrospection later
- Fill in `## Outcome` and update the INDEX status when development ends

❌ **Don't**

- Don't treat silence as migration consent or leave stale pointers to the old
  tracking mechanism
- Don't ask to delete the source until `migration-audit` exits 0 — an empty
  "in progress" section is not proof the rest of the document holds no
  actionable content
- Don't hand-edit a migration record's `ID`, `Kind`, `Source`, `Loc`, or
  `Section` cells; re-run `migration-inventory` instead
- Don't delete tracker-directory folders directly (update the INDEX status to
  `abandoned` first, then clean up manually)
- Don't fill real content into `_template/PROGRESS.md` (the template should
  only ever contain `{{PLACEHOLDER}}` tokens)
- Don't change status in only one file; use the lifecycle script or run `check` after manual edits
- Don't pass a `slug` containing uppercase letters, underscores, or spaces (the script rejects it)
- Don't use a separator other than comma between `--scope` entries (comma
  separates entries, colon separates name/branch/ticket within one)
