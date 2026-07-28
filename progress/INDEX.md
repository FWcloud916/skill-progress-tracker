# Progress Item Index

Items are created by `new_progress.py`, then maintained with
`update_progress.py` by developers or agents. See [`README.md`](README.md)
for usage and invoke the installed `progress-tracker` skill for the full
workflow.

## Items

| Status | Item | Folder | Scope | Ticket | Plan | Created | Notes |
|---|---|---|---|---|---|---|---|
| `done` | Progress Tracker Improvements | `progress/2026-07-24-progress-tracker-improvements/` | `progress-tracker` | N/A | _plans/progress-tracker-improvements-plan.md | 2026-07-24 | P0 verification truthfulness; P1 lifecycle automation and input hardening |
| `review` | SKILL.md progressive-disclosure refactor | `progress/2026-07-28-skill-docs-progressive-disclosure/` | `progress-tracker` | N/A | [skill-docs-progressive-disclosure-progress-tracker-improvement-plan.md](_plans/skill-docs-progressive-disclosure-progress-tracker-improvement-plan.md) | 2026-07-28 |  |

## Status legend

Keep each item's status here identical to the Status field in its
`PROGRESS.md`.

<!-- STATUS_LIFECYCLE_START -->
Status enum: `planning`, `in-progress`, `review`, `blocked`, `done`, `abandoned`

```
planning → in-progress ⇄ review → done
                ↕
             blocked

Any non-terminal status → abandoned
```
<!-- STATUS_LIFECYCLE_END -->

| Status | Meaning |
|---|---|
| `planning` | Item created, implementation not started (scaffold-script default) |
| `in-progress` | Under active development |
| `review` | PR/MR opened, in code review / QA — **not** `done`; that comes after merge |
| `blocked` | Paused on an external dependency |
| `done` | Development complete (PR/MR merged) |
| `abandoned` | Stopped without completing |
