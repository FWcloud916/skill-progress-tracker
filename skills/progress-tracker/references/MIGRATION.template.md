# Migration inventory: {{SLUG}}

**Slug:** {{SLUG}}
**Created:** {{CREATED}}
**Updated:** {{UPDATED}}

This record is generated and reconciled by `update_progress.py
migration-inventory` and `update_progress.py migration-audit`. It is the
deletion gate: the legacy source(s) below MUST NOT be deleted until
`migration-audit <slug>` exits 0.

## Sources

<!-- MIGRATION_SOURCES_START -->
| Source | SHA-256 |
|---|---|
{{SOURCE_ROWS}}
<!-- MIGRATION_SOURCES_END -->

Keep every source byte-identical while this migration is open. If a source
must change, re-run `migration-inventory` — it preserves the Disposition,
Destination, and sign-off state of every entry whose identity is unchanged.

## How to fill this in

1. Rows below are generated from the source(s). Do not hand-add, hand-delete,
   or hand-edit the `ID`, `Kind`, `Source`, `Loc`, `Section`, or `Entry`
   cells — re-run `migration-inventory` instead. `migration-audit` detects
   hand edits to `Kind` and refuses to pass.
2. Every row whose `Kind` is `actionable` or `ambiguous` MUST get a
   `Disposition` and a `Destination`. `TBD` in either cell blocks the audit.
   An unrecognized heading in the source becomes `ambiguous` — this is
   deliberate: an empty-looking WIP section elsewhere in the same document
   does not excuse an unclassified section from review.
3. Rows whose `Kind` is `done`, `empty`, or `historical` are pre-filled and
   need no action, but may be re-dispositioned if you want to migrate them
   too.

<!-- MIGRATION_DISPOSITIONS_START -->
| Disposition | Meaning | Destination cell |
|---|---|---|
| `TBD` | Unresolved (generated default) | blocks the audit |
| `migrated` | Copied into a tracker item | the destination item's slug — it MUST already exist |
| `excluded` | User-approved drop | the user's reason (required) |
| `archived` | Kept as a historical/reference record in the source | a reason, or `—` |
| `not-applicable` | Heading-only, empty, or already-done row | `—` |
<!-- MIGRATION_DISPOSITIONS_END -->

## Entries

<!-- MIGRATION_TABLE_START -->
| ID | Kind | Source | Loc | Section | Entry | Disposition | Destination |
|---|---|---|---|---|---|---|---|
{{ENTRY_ROWS}}
<!-- MIGRATION_TABLE_END -->

`Loc` is informational only (a line number in the source); `migration-audit`
never compares it — a source's content, not its line numbers, is its identity.

## Verified by `migration-audit` (do not hand-tick — these are computed, not attested)

- Every source entry has a record row, and every record row matches a source entry
- Every `actionable` / `ambiguous` row has a Disposition and a Destination
- Every `migrated` Destination resolves to an existing tracker item slug
- Every `excluded` Destination states a reason
- No row's `Kind` was hand-edited
- `update_progress.py check` (tracker-internal consistency) passes

## Confirmed by the human (required — `migration-audit` reads these boxes; it cannot verify them itself)

<!-- MIGRATION_SIGNOFF_START -->
- [ ] The historical/reference sections listed by `migration-audit` were shown to the user
- [ ] Every migrated entry was checked for semantic equivalence against its destination
- [ ] The pointer audit passed: every live reference to the legacy source was updated
- [ ] The link audit passed: every changed relative link resolves
- [ ] The user chose whether to retain or delete the legacy source
<!-- MIGRATION_SIGNOFF_END -->
