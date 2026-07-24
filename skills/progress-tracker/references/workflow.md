# Progress tracking workflow

> **Type:** How-to
> **Audience:** Developers, AI assistants
> **Last updated:** 2026-07-24
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

Open `<tracker-dir>/YYYY-MM-DD-<slug>/PROGRESS.md`, back-fill `TBD` values,
tick off tasks, add a `## Work log` entry, update **Updated** and the
`INDEX.md` status column. Field-by-field spec and the status enum
(`planning` / `in-progress` / `review` / `blocked` / `done` / `abandoned`) →
[`SKILL.md`](../SKILL.md) §During work, §Status lifecycle.

### 3. After work: close out

- Fill in `PROGRESS.md`'s `## Outcome` (final status, PR/commit refs, follow-ups)
- Update the **Updated** field
- Change the item's row in `INDEX.md` to `done` (or `abandoned`)

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
│   └── refund-flow-abstract-breeze.md
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
| **Related plan** | Relative path to the version-controlled snapshot (`../_plans/<name>.md`), or `N/A`. The snapshot is copied in by the script at creation time and is a frozen record of original intent; `PROGRESS.md` itself is the living source of truth as development proceeds. |
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

Single source of truth for the status enum and transition diagram →
[`SKILL.md`](../SKILL.md) §Status lifecycle.

---

## Relationship to plans

`_plans/` is a version-controlled subdirectory of the tracker that holds a
**frozen snapshot** of the plan active when each task was created. The
script's `--plan` option copies the plan file in from wherever it was
originally written, so the snapshot travels with the repository regardless of
machine. Resolution rules for bare filenames vs. paths →
[`SKILL.md`](../SKILL.md) §Before starting work.

The script copies the plan to `_plans/<name>.md`; `PROGRESS.md`'s **Related
plan** field records the relative path `../_plans/<name>.md` (clickable in an
editor).

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

- Scripts and AI agents **MUST NOT** proactively delete any folder or file
  under the tracker directory.
- Cleanup (deleting folders, removing INDEX rows) is a **human decision**,
  performed manually as needed.
- Consider keeping `done` / `abandoned` items around for at least one sprint
  for later reference and retrospectives.

---

## ✅ Do / ❌ Don't

✅ **Do**

- Preview with `--dry-run` before creating a task
- Include **every scope entry involved** in `--scope`, even read-only ones
- Fill in `TBD` for branch/ticket before they exist, then back-fill `## Scope` once known
- Always link a plan-mode/planning-tool plan via `--plan` when one exists
- Pass an umbrella/epic reference via `--ticket` when one exists; it's kept exactly as given
- Update `## Work log` daily, at a granularity that supports retrospection later
- Fill in `## Outcome` and update the INDEX status when development ends

❌ **Don't**

- Don't delete tracker-directory folders directly (update the INDEX status to
  `abandoned` first, then clean up manually)
- Don't fill real content into `_template/PROGRESS.md` (the template should
  only ever contain `{{PLACEHOLDER}}` tokens)
- Don't update `PROGRESS.md` without also writing back the `INDEX.md` status column
- Don't pass a `slug` containing uppercase letters, underscores, or spaces (the script rejects it)
- Don't use a separator other than comma between `--scope` entries (comma
  separates entries, colon separates name/branch/ticket within one)
