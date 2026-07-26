# _migrations/

Migration inventory records: one file per adopted legacy tracker, named
`<migration-slug>.md`, generated and reconciled by `update_progress.py
migration-inventory` and `update_progress.py migration-audit`.

- Written by `migration-inventory <slug> --source <legacy-path>` — do not
  hand-create or hand-edit the generated `ID`/`Kind`/`Source`/`Loc`/`Section`/
  `Entry` cells; re-run the command instead
- Fill in `Disposition` and `Destination` for every row `migration-audit`
  reports as unresolved, then tick the human sign-off checklist
- `migration-audit <slug>` is the migration's deletion gate: it exits
  non-zero while any actionable or ambiguous source entry lacks a
  disposition and destination, or a sign-off box is unticked
- **Do not delete a record here** while its legacy source still exists — it
  is the audit trail proving the migration was complete
