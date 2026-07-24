# Progress Tracker Improvements

**Slug:** progress-tracker-improvements
**Status:** planning
**Ticket:** N/A
**Related plan:** ../_plans/progress-tracker-improvements-plan.md
**Created:** 2026-07-24
**Updated:** 2026-07-24

---

## Scope

| Scope | Branch | Ticket | Notes |
|---|---|---|---|
| `progress-tracker` | TBD | TBD | Baseline assessment performed on `main`; implementation branch has not been created. |

## Background & goals

The skill already has a strong creation workflow, project-root containment,
deterministic tests, lifecycle scenarios, and documented design decisions. A
baseline review on 2026-07-24 confirmed that the required verification gate,
63 pytest tests, all 8 lifecycle scenarios, and Ruff 0.16.0 pass.

The next improvement cycle should make the advertised full lifecycle as
reliable as item creation. The primary goals are to automate update and
close-out operations, prevent `PROGRESS.md` / `INDEX.md` status drift, harden
Markdown rendering for free-form inputs, make verification claims match the
checks actually executed, and improve runtime and plan-snapshot portability.

The frozen implementation plan is recorded in
[`../_plans/progress-tracker-improvements-plan.md`](../_plans/progress-tracker-improvements-plan.md).

## Task list

- [x] Complete the baseline architecture, behavior, test, and eval review.
- [x] Record the prioritized improvement plan and acceptance criteria.
- [ ] P0: run lifecycle scenarios from `scripts/verify.sh` and fail when the
  required Python test runner is unavailable.
- [ ] P1: add validated update, status-transition, close-out, and audit/check
  operations that keep `PROGRESS.md` and `INDEX.md` synchronized.
- [ ] P1: define delimiter behavior and escape or reject Markdown-breaking
  title, scope, branch, ticket, and plan values.
- [ ] P2: establish and test the real minimum Python version instead of
  requiring Python 3.14 without a demonstrated need.
- [ ] P2: namespace plan snapshots by task identity and render explicit
  Markdown links while preserving existing tracker compatibility.
- [ ] Update unit tests, lifecycle scenarios, trigger coverage, CLI help,
  SKILL.md, references, README, and design decisions with each behavior change.
- [ ] Bump the plugin version for the user-visible release.
- [ ] Run the complete verification and lint suite before review.

## Work log

### 2026-07-24

- Evaluated the current skill contract, script behavior, templates, dedicated
  agent instructions, tests, scenarios, verification gate, and CI workflow.
- Verified 63 pytest tests, 8 lifecycle scenarios, the repository consistency
  gate, and Ruff 0.16.0.
- Identified the highest-value gaps: manual two-file lifecycle updates,
  unescaped Markdown/free-form delimiters, and lifecycle scenarios that are
  documented as part of the gate but are not currently invoked by it.
- Created this tracker item and saved the original improvement plan as an
  immutable snapshot.

## Outcome

> Fill in after development finishes.

**Final status:**
**PR / Commit:**
**Follow-ups:**
