# _migrations/

Migration inventory records: one file per adopted legacy tracker, named
`<migration-slug>.md`, generated and reconciled by `update_progress.py
migration-inventory`, `migration-audit`, and `migration-finalize`.

- Written by `migration-inventory <slug> --source <legacy-path>` — do not
  hand-create or hand-edit the generated `ID`/`Kind`/`Source`/`Loc`/`Section`/
  `Entry` cells; re-run the command instead
- Fill in `Disposition`, `Destination`, and per-row Evidence for every row
  `migration-audit` reports as unresolved, then tick the pre-deletion human
  sign-off checklist
- `migration-audit <slug>` is the migration's pre-deletion gate: it exits
  non-zero while any actionable or ambiguous source entry lacks a
  disposition and destination, migrated Evidence is absent/non-unique, or a
  sign-off box is unticked
- Persist the user's choice with `migration-finalize --decision retain` or
  `--decision delete`. It never deletes sources; after an approved external
  deletion, `--confirm-deleted` verifies the sealed record and exact sources
- A refreshed source or generated inventory resets all sign-offs; only an
  identical source and inventory preserves them
- **Do not delete a record here** — its outcome, exact sources, and approval
  fingerprint are the durable audit trail
