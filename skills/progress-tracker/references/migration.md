# Legacy-tracker migration

Migration is a two-phase commit: the audit is the prepare phase; nothing is
deleted until it votes yes.

> **Type:** How-to
> **Audience:** Developers, AI assistants
> **Last updated:** 2026-07-28
>
> This document is the migration contract in full: discovery, consent, the
> step-by-step flow, the authoritative command reference, and the
> Kind/disposition rules. The normative gate block
> (`MIGRATION_GATE_START/END`) lives byte-identically in
> [`SKILL.md`](../SKILL.md), [`workflow.md`](workflow.md), and the bundled
> subagent definition; it is deliberately not duplicated here.
>
> **Terminology:** this document uses RFC 2119 keywords — **MUST**,
> **SHOULD**, **MAY**.

---

## Discovery and consent

Before first use, the agent **MUST** inspect the project for an existing local
tracking mechanism and for project documents, agent instructions, scripts, or
configuration that point to it (detection rules → [`SKILL.md`](../SKILL.md)
§Before creating anything).

When a separate mechanism exists, the agent **MUST NOT** scaffold a parallel
tracker without first showing the discovered artifacts and asking whether the
user wants to migrate. Migration requires explicit approval; silence is not
consent. A declined migration preserves the existing mechanism; coexistence
also requires an explicit user choice.

---

## Why the gate exists (KI-001)

An approved migration is **script-gated**, not a judgment call: a real
migration trial once treated an empty "current work" section as proof a legacy
source held no actionable content, while a "Next steps" section and a backlog
it never inspected still held unmigrated work (see `KNOWN-ISSUE.md` KI-001 in
the repository root for the incident this contract was hardened against).
`migration-inventory` and `migration-audit` exist specifically so that
judgment call is no longer load-bearing.

---

## Migration flow

Command invocations for every step live in the
[command reference](#command-reference-authoritative) below.

1. **Inventory first.** Run `migration-inventory` to produce a
   section-by-section inventory record at `<tracker-dir>/_migrations/<slug>.md`
   **before** editing anything. It scans the **whole document**, not just an
   "in progress" or "current work" section, and defaults every unrecognized
   heading to `ambiguous` (blocking). If the tracker does not exist yet, the
   command scaffolds only its support files; create the destination item(s)
   after the inventory exists.
2. **Agree on a source-to-destination mapping.** Copy only facts the source
   states; leave unknowns explicit rather than inventing them.
3. **Copy, keeping the source unchanged.** Copy every actionable entry the
   inventory lists into the new item(s): current status, scope,
   branch/ticket/plan references, goals, unfinished tasks, current work log,
   blockers, next actions, and live links. For each `actionable`/`ambiguous`
   row, fill in its Disposition (`migrated`, `excluded`, or `not-applicable`)
   and Destination. Every `migrated` row also needs a non-trivial,
   row-specific Evidence locator copied from the destination item.
4. **Verify field by field.** For each `migrated` row, verify semantic
   equivalence with wherever it landed, and tick the record's corresponding
   sign-off box only once verified. Missing or unexplained active content —
   any row still `TBD` — fails the audit.
5. **Update every live pointer** to the old mechanism: Markdown links, path
   mentions, agent instructions, command examples, scripts, and configuration.
6. **Audit the project.** Run `update_progress.py check`, search the whole
   project for every old path or filename, and verify every changed relative
   link resolves. Classify any remaining match as an intentional
   historical/compatibility reference, then tick the record's remaining
   sign-off boxes (historical sections disclosed, pointer audit passed, link
   audit passed).
7. **Run `migration-audit` — the pre-deletion gate** (the gate block in
   `SKILL.md` is normative). Only after it exits 0, show its output and ask
   whether to delete the original artifacts. An explicit answer is required.
   Persist a declined deletion with `migration-finalize --decision retain`.
   For an approved deletion, run `migration-finalize --decision delete`; it
   reruns the audit, seals the exact sources and record fingerprint, and
   **does not delete anything**. Remove only the approved sources, update
   affected pointers, run old-reference/link audits, then run
   `migration-finalize --confirm-deleted`.

The migration is complete only when `migration-audit` exits 0, all active
content is accounted for, the two records agree, every changed pointer has
been reviewed, and the record outcome has left `pending`. The final report
lists the migration record's location, schema, and final outcome,
`migration-audit`'s pass/fail result, the historical/reference entry counts it
disclosed, pointer files updated, and intentional legacy references.

---

## Command reference (authoritative)

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

---

## Kind values and disposition rules

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

## ✅ Do / ❌ Don't

✅ **Do**

- Discover existing tracking artifacts and ask before migrating or scaffolding
  a parallel tracker
- Run `migration-inventory` before copying anything — inventory the whole
  source document, not just an "in progress" or "current work" section
- Dispose of every `actionable`/`ambiguous` inventory row and run
  `migration-audit` before asking whether to delete the source
- Record the user's retain/delete choice with `migration-finalize`
- Audit every old path/name and changed link after an approved migration

❌ **Don't**

- Don't treat silence as migration consent or leave stale pointers to the old
  tracking mechanism
- Don't ask to delete the source until `migration-audit` exits 0 — an empty
  "in progress" section is not proof the rest of the document holds no
  actionable content
- Don't hand-edit a migration record's `ID`, `Kind`, `Source`, `Loc`,
  `Section`, or `Entry` cells; re-run `migration-inventory` instead
- Don't delete a `<tracker-dir>/_migrations/<slug>.md` record while its legacy
  source still exists — it is the audit trail proving the migration was
  complete
