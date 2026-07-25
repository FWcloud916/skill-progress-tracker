# _plans/

Version-controlled snapshots of the plan that was active when each progress
item was created.

- One file per task: `<slug>-<plan-name>.md` (the slug namespace prevents
  collisions when tasks reuse a common source filename such as `plan.md`)
- Written by `new_progress.py --plan <path>` (copied from wherever the plan
  was originally written)
- Treat as a **frozen snapshot** of the original intent — do not edit after
  creation
- The living record of what actually happened is `PROGRESS.md` in the item
  folder

**Do not delete files here manually** — they are the provenance link from
`PROGRESS.md`'s `Related plan` field.
