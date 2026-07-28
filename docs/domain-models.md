# progress-tracker — Domain Models & Business Mechanisms

> **Type:** Reference
> **Audience:** Developers, AI assistants, code reviewers
> **Last updated:** 2026-07-28

---

The project has no database models. Its domain consists of Markdown records, parsed
in-memory dataclasses, and guarded transitions between filesystem states. The canonical
workflow contract is [`SKILL.md`](../skills/progress-tracker/SKILL.md) (with the
migration contract in
[`references/migration.md`](../skills/progress-tracker/references/migration.md)); this
document maps that contract to the implementing functions in the two Python CLIs.

## 0. Shared Vocabulary

Terms used with a fixed meaning across `SKILL.md`, the `references/` docs,
and this document:

| Term | Definition |
|---|---|
| **scope** | A free-form label for one piece of a task (e.g. `api`, `payments-service`); never validated against any directory. |
| **tracker-dir** | The tracker's root directory inside the project — `progress/` by default, overridden by `--dir` / `$PROGRESS_TRACKER_DIR` — holding `INDEX.md`, item folders, `_template/`, `_plans/`, and `_migrations/`. |
| **preflight** | The mandatory pre-creation inspection for an existing tracking mechanism and the documents that point to it (`SKILL.md` §Before creating anything). |
| **two-phase commit** | The migration deletion model: `migration-audit` is the prepare phase, and deletion may proceed only after it exits 0 and `migration-finalize` records the user's explicit decision (the commit). |
| **Kind** | A migration-inventory row's generated classification: `actionable` and `ambiguous` block the audit; `done`, `empty`, and `historical` do not. |
| **disposition** | The reviewer's ruling on an inventory row: `migrated`, `excluded`, or `not-applicable`. |

## 1. Model Details

```text
┌───────────────────┐ 1       1 ┌───────────────────┐
│ Tracker directory │───────────│       Index       │
└─────────┬─────────┘           └─────────┬─────────┘
          │ 1                             │ 1
          │ *                             │ *
          ▼                               ▼
┌───────────────────┐ 1       1 ┌───────────────────┐
│   Progress item   │───────────│     Index row     │
└─────────┬─────────┘           └───────────────────┘
          │ 0..1
          ▼
┌───────────────────┐
│   Plan snapshot   │
└───────────────────┘

┌───────────────────┐ *       * ┌───────────────────┐
│ Migration record  │───────────│   Legacy source   │
└─────────┬─────────┘           └───────────────────┘
          │ *
          │ Destination + Evidence
          ▼ *
┌───────────────────┐
│   Progress item   │
└───────────────────┘
```

### Tracker Directory

The tracker directory is a relative path that resolves strictly below the selected
project root. Its name comes from `--dir`, then `$PROGRESS_TRACKER_DIR`, then
`progress`. `resolve_tracker_dir()` in
[`new_progress.py`](../skills/progress-tracker/scripts/new_progress.py) rejects absolute
paths, the project root itself, parent traversal, and symlink escapes.

On first use, `scaffold_tracker_dir()` copies four bundled seeds without overwriting an
existing file:

| Path | Role |
|---|---|
| `README.md` | Stable tracker-local usage and cleanup guide |
| `INDEX.md` | One list of all progress items and their mirrored status |
| `_template/PROGRESS.md` | Item template used by subsequent creation |
| `_plans/README.md` | Plan-snapshot policy |

`_migrations/README.md` is added only when migration inventory first writes a record.

### Progress Item

A progress item is one `PROGRESS.md` under a dated
`YYYY-MM-DD-<slug>/` directory. Its persisted fields come from
[`PROGRESS.template.md`](../skills/progress-tracker/references/PROGRESS.template.md):

| Field or section | Rule |
|---|---|
| `Slug` | Stable lowercase letters/digits/hyphens identifier; item discovery requires exactly one match |
| `Status` | One canonical lifecycle value; must equal the matching index-row status |
| `Ticket` | Optional umbrella reference, trimmed but otherwise stored verbatim |
| `Related plan` | Relative link to the immutable plan snapshot, or `N/A` |
| `Created` / `Updated` | Local calendar dates; mutations replace `Updated` with today's date |
| `Scope` table | One or more free-form labels with branch and per-scope ticket; labels are not paths |
| `Background & goals` | Living explanation of motivation and intended outcome |
| `Task list` | Markdown checkboxes; lifecycle updates complete entries by exact logical text |
| `Work log` | Dated entries; additional notes on the same date append below that heading |
| `Outcome` | Final summary, status, PR/commit reference, and follow-up text |

The directory date is organizational; the stable identity used by update commands is
the `Slug` field. `find_item()` refuses zero or multiple matching items.

### Index and Index Row

`INDEX.md` is scaffolded from
[`INDEX.template.md`](../skills/progress-tracker/references/INDEX.template.md). Its item
table has one row per progress item with status, title, folder, scopes, umbrella ticket,
plan, creation date, and notes.

The row is linked to an item by its folder marker. `find_index_row()` requires exactly
one match; `index_status()` parses the first cell. Creation inserts after all existing
table rows by locating the exact `TABLE_HEADER_MARKER` string. This exact-string
dependency is protected by `scripts/verify.sh`.

### Plan Snapshot

A plan snapshot is an optional copy stored at `_plans/<slug>-<source-name>`. Prefixing
the item slug prevents two tasks that both use a source such as `plan.md` from
colliding. `copy_plan()` refuses an existing destination rather than overwriting
original intent.

The snapshot is immutable provenance. The associated progress item remains the living
record and may diverge from the original plan as the work changes.

### SourceEntry

`SourceEntry` is a frozen dataclass produced by `scan_source()` in
[`update_progress.py`](../skills/progress-tracker/scripts/update_progress.py). It holds:

| Field | Meaning |
|---|---|
| `entry_id` | Content-derived `E<digest>` identity based on source, normalized section, normalized text, and duplicate occurrence |
| `kind` | `actionable`, `ambiguous`, `done`, `empty`, or `historical` |
| `source` | Project-root-relative legacy Markdown path |
| `line` | Informational source line number; not part of reconciliation identity |
| `section` | Full inherited heading path |
| `text` | Complete prose block, list entry, checkbox text, or labeled table row |

Unknown headings default to `ambiguous`. Unchecked boxes and inline
`TODO`/`TBD` signals become `actionable` even inside an otherwise historical section.
Checked boxes become `done`. Exact empty-state phrases are recognized before inline
actionable matching, preventing text such as “Nothing in progress” from becoming a
false blocking row.

### Migration Record and RecordRow

A migration record is `_migrations/<slug>.md`, generated from
[`MIGRATION.template.md`](../skills/progress-tracker/references/MIGRATION.template.md).
`parse_migration_record()` maps it to `MigrationRecord`, containing the schema version,
source digests, entry rows, sign-offs, and outcome.

Each `RecordRow` mirrors a `SourceEntry` and adds three editable reconciliation cells:

| Cell | Allowed meaning |
|---|---|
| `Disposition` | `migrated`, `excluded`, or `not-applicable`, constrained by entry kind |
| `Destination` | Existing progress-item slug for `migrated`; required reason for `excluded`; empty marker for `not-applicable` |
| `Evidence` | Unique, row-specific locator found exactly once in the migrated destination item; empty for other dispositions |

Generated identity fields (`ID`, `Kind`, `Source`, `Section`, and `Entry`) must continue
to match a fresh source scan. `Loc` remains informational so unrelated line movement
does not invalidate an otherwise identical entry.

### MigrationOutcome

`MigrationOutcome` persists the source-level decision separately from per-entry
dispositions:

| State | Meaning |
|---|---|
| `pending` | Inventory/reconciliation is open; no retain/delete outcome recorded |
| `retained` | User chose to keep the legacy source; terminal |
| `delete-approved` | Audit passed and the exact source set plus approval fingerprint were sealed; sources still require separate removal |
| `deleted` | Every approved source is absent, the seal is unchanged, and tracker consistency still passes; terminal |

The script never performs source deletion.

## 2. Item Creation Mechanism

`new_progress.py` follows a validate-then-write flow:

1. Parse the slug, title, escaped scope syntax, tickets, optional plan, project root,
   and tracker directory.
2. Resolve every scaffold source and destination and enforce project-root containment.
3. Refuse an existing item directory, plan-snapshot collision, malformed index table,
   missing seed, broken symlink, or unresolved plan before any write occurs.
4. Render the item and updated index in memory.
5. Scaffold missing support files.
6. In normal mode, create the item, copy the optional plan, and write the updated
   index. In `--dry-run` mode, print the prospective content and write nothing.

Creation starts every item in `planning`. It does not infer tasks, goals, branch names,
or ticket conventions beyond values explicitly passed by the caller.

## 3. Status Lifecycle and Mutations

The canonical state definitions live in `SKILL.md`, `workflow.md`, and
`INDEX.template.md`; `STATUS_VALUES` and `ALLOWED_TRANSITIONS` enforce the same graph in
`update_progress.py`:

```text
planning ──> in-progress <──> review ──> done
                  ^  |
                  |  v
                blocked

planning, in-progress, review, or blocked ──> abandoned
```

Allowed non-terminal updates are:

| Current | Next |
|---|---|
| `planning` | `in-progress`, `abandoned` |
| `in-progress` | `review`, `blocked`, `abandoned` |
| `review` | `in-progress`, `done`, `abandoned` |
| `blocked` | `in-progress`, `abandoned` |
| `done`, `abandoned` | None |

`run_mutation()` first calls `prepare_item()`, which refuses pre-existing status drift.
It then validates the requested transition and performs any scope replacement, exact
task completion, work-log append, or outcome replacement in memory. Status is changed
in both documents. `write_validated_pair()` writes the item and index and attempts to
restore both originals after an ordinary filesystem write error; it is not a
crash-safe cross-file transaction.

The `close` command is the only normal path to a final outcome. It accepts `done` or
`abandoned`, requires outcome text, fills the outcome fields, and adds a final work-log
entry unless the caller supplied one.

## 4. Tracker Consistency Audit

`audit_tracker()` walks non-underscore item directories and compares them with the
index in both directions. It reports:

- missing or repeated `Slug`/`Status` fields;
- status values outside the canonical enum;
- duplicate item slugs;
- missing or duplicate index rows;
- malformed index status cells;
- item/index status drift; and
- stale index rows with no corresponding item.

The public `check` command is read-only. Migration audit and deletion confirmation call
the same function so a clean migration record cannot mask a broken destination tracker.

## 5. Legacy Migration Mechanism

### 5.1 Whole-Document Inventory

`migration-inventory` accepts one or more Markdown files, or directories recursively
expanded to Markdown files. A source must be inside the project root and outside the
destination tracker. The scanner removes YAML frontmatter, fenced code, and HTML
comments, then inventories prose blocks, lists, checkboxes, and complete table rows in
source order.

Heading classification is deliberately fail-closed:

```text
recognized actionable heading ──> actionable
recognized historical heading ──> historical
unrecognized heading ────────────> ambiguous (blocking)
```

If no tracker exists, inventory may scaffold only the tracker support files before
writing the migration record. It does not create a destination progress item.

Refreshing an open record preserves compatible disposition, destination, and evidence
values for unchanged entry IDs. Human sign-offs survive only when the schema, source
digests, generated fields, and rendered dispositions are identical; any substantive
inventory change resets them.

### 5.2 Reconciliation and the Pre-Deletion Gate

`migration-audit` rescans the recorded sources and calls `reconcile()`. The gate remains
closed if any of these conditions holds:

- a source is unreadable or its SHA-256 digest changed;
- a scanned entry has no row, or a row has no scanned entry;
- a generated row field was edited;
- a disposition is missing, unknown, or invalid for the entry kind;
- a migrated destination slug does not exist;
- migrated evidence is absent, shorter than eight normalized characters, missing,
  repeated in the destination, or reused by another row;
- an exclusion has no reason;
- a non-migrated row contains evidence;
- a required human sign-off is missing or unchecked; or
- the destination tracker consistency audit fails.

Historical entries are disclosed on both pass and failure paths because deletion would
remove them even though they are non-blocking by default.

### 5.3 Non-Destructive Finalization

`migration-finalize --decision retain` reruns reconciliation and records `retained`.
`--decision delete` also reruns reconciliation, records `delete-approved`, and seals the
exact sources plus a SHA-256 fingerprint of the schema, rows, and sign-offs. Neither
command deletes a source.

After a human or separately authorized operation removes only the approved sources,
`--confirm-deleted` requires:

1. the record is `delete-approved`;
2. the confirmed source set still matches;
3. the approval fingerprint still matches;
4. every approved source is absent; and
5. tracker consistency passes.

Only then does the record enter `deleted`.

## 6. Filesystem Safety and Rendering

- `require_project_descendant()` resolves paths before accepting them, including paths
  behind existing symlinks.
- Scope labels are parsed text and never validated as directories.
- Ambiguous scope input fails closed: an unescaped comma touching whitespace
  and empty scope entries are rejected at parse time, and both CLIs echo the
  parsed scope names in normal-mode output.
- Ticket values are trimmed and defaulted but never prefixed or reformatted.
- Markdown table values escape pipes and backslashes; inline code chooses a delimiter
  longer than any backtick run in the value.
- User-controlled Markdown values must be single-line, preventing field or row
  injection.
- Relative plan links are URL-encoded and explicit.
- Creation and migration commands provide `--dry-run`; audit commands are inherently
  read-only.
- Current tracker items and index rows are never deleted automatically.

## 7. Deprecated Components

Migration schema v1 remains readable only to support an explicit refresh to v2.
`parse_migration_record()` supplies a pending in-memory outcome for v1, while
`migration-inventory` carries compatible row choices forward and adds unresolved
evidence where required. `migration-finalize` refuses a record until it has been
refreshed to v2.

The removed entry-level `archived` disposition must not be reintroduced. Retention is a
document-level outcome; blocking rows use `migrated` or reasoned `excluded`, while
non-blocking rows use `not-applicable` unless deliberately migrated or excluded.

## 8. Developer Tooling / Maintenance Scripts

| File | Responsibility |
|---|---|
| [`test_new_progress.py`](../skills/progress-tracker/scripts/test_new_progress.py) | Pure helper tests plus end-to-end creation, rendering, containment, idempotency, and plan tests |
| [`test_update_progress.py`](../skills/progress-tracker/scripts/test_update_progress.py) | Transition, synchronized mutation, audit, scanner, reconciliation, and finalization tests |
| [`scripts/verify.sh`](../scripts/verify.sh) | Cross-file placeholder, marker, lifecycle, packaging, version, test, and scenario consistency gate |
| [`evals/scripts/run_scenarios.py`](../evals/scripts/run_scenarios.py) | Runs JSON lifecycle scenarios against disposable Git repositories |
| [`evals/scripts/grade_scenarios.py`](../evals/scripts/grade_scenarios.py) | Grades deterministic file-existence and content invariants |

Behavior changes to either CLI require corresponding tests in its adjacent pytest file.
Changes to CLI flags, output paths, or file scope also require matching scenario and
grader assertions, as specified by [`AGENTS.md`](../AGENTS.md).
