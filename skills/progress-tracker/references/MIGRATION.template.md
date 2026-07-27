# Migration inventory: {{SLUG}}

**Slug:** {{SLUG}}
**Schema version:** 2
**Created:** {{CREATED}}
**Updated:** {{UPDATED}}

This record is generated and reconciled by `update_progress.py
migration-inventory` and `update_progress.py migration-audit`. It is the
durable migration audit trail: the legacy source(s) below MUST NOT be deleted
until `migration-audit <slug>` exits 0 and `migration-finalize --decision
delete` records explicit approval.

## Sources

<!-- MIGRATION_SOURCES_START -->
| Source | SHA-256 |
|---|---|
{{SOURCE_ROWS}}
<!-- MIGRATION_SOURCES_END -->

## Migration outcome

<!-- MIGRATION_OUTCOME_START -->
**State:** pending
**Decision date:** —
**Completion date:** —
**Confirmed sources:** —
**Approval fingerprint:** —
<!-- MIGRATION_OUTCOME_END -->

`migration-audit` opens only the pre-deletion gate. Record the user's durable
choice with `migration-finalize <slug> --decision retain` or
`migration-finalize <slug> --decision delete`. The delete decision does not
delete anything; after the approved sources are removed separately, use
`migration-finalize <slug> --confirm-deleted` to record completion.

Keep every source byte-identical while this migration is open. If a source
must change, re-run `migration-inventory` — it preserves the Disposition and
Destination and Evidence of every unchanged entry, but resets every human sign-off whenever
the source or generated inventory changes.

## How to fill this in

1. Rows below are generated from the source(s). Do not hand-add, hand-delete,
   or hand-edit the `ID`, `Kind`, `Source`, `Loc`, `Section`, or `Entry`
   cells — re-run `migration-inventory` instead. `migration-audit` detects
   hand edits to every generated field except informational `Loc` and refuses
   to pass.
2. Every row whose `Kind` is `actionable` or `ambiguous` MUST get a
   `Disposition` of `migrated` or `excluded` and a valid `Destination`. A
   `migrated` row also needs non-trivial `Evidence`: a unique, row-specific single-line
   locator copied from the destination item's `PROGRESS.md`. `TBD` in any
   required cell blocks the audit.
   An unrecognized heading in the source becomes `ambiguous` — this is
   deliberate: an empty-looking WIP section elsewhere in the same document
   does not excuse an unclassified section from review.
3. Rows whose `Kind` is `done`, `empty`, or `historical` are pre-filled as
   `not-applicable`. `done` and `historical` rows may instead be `migrated` or
   `excluded`; `empty` rows may only be `not-applicable`.

<!-- MIGRATION_DISPOSITIONS_START -->
| Disposition | Meaning | Destination cell | Evidence cell |
|---|---|---|---|
| `TBD` | Unresolved (generated default) | blocks the audit | blocks the audit |
| `migrated` | Copied into a tracker item | the destination item's slug — it MUST already exist | unique, row-specific locator copied from that item's `PROGRESS.md` |
| `excluded` | User-approved drop | the user's reason (required) | `—` |
| `not-applicable` | Empty, already-done, or disclosed historical/reference row | `—` | `—` |
<!-- MIGRATION_DISPOSITIONS_END -->

## Entries

<!-- MIGRATION_TABLE_START -->
| ID | Kind | Source | Loc | Section | Entry | Disposition | Destination | Evidence |
|---|---|---|---|---|---|---|---|---|
{{ENTRY_ROWS}}
<!-- MIGRATION_TABLE_END -->

`Loc` is informational only (a line number in the source); `migration-audit`
never compares it — a source's content, not its line numbers, is its identity.

## Verified by `migration-audit` (do not hand-tick — these are computed, not attested)

- Every source entry has a record row, and every record row matches a source entry
- Every `actionable` / `ambiguous` row has a Disposition and a Destination
- Every `migrated` Destination resolves to an existing tracker item slug and
  its Evidence occurs exactly once in that item's `PROGRESS.md`
- Every `excluded` Destination states a reason
- No row's generated `ID`, `Kind`, `Source`, `Section`, or `Entry` was hand-edited
- `update_progress.py check` (tracker-internal consistency) passes

## Confirmed by the human before the deletion question

`migration-audit` reads these boxes but cannot verify them itself. The later
choice to retain or delete the source is deliberately not a sign-off here:
that question is asked only after this pre-deletion audit exits 0.

<!-- MIGRATION_SIGNOFF_START -->
- [ ] The historical/reference sections listed by `migration-audit` were shown to the user
- [ ] Every migrated entry was checked for semantic equivalence against its destination
- [ ] The pointer audit passed: every live reference to the legacy source was updated
- [ ] The link audit passed: every changed relative link resolves
<!-- MIGRATION_SIGNOFF_END -->
