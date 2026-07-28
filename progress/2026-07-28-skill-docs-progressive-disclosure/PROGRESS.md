# SKILL.md progressive-disclosure refactor

**Slug:** skill-docs-progressive-disclosure
**Status:** review
**Ticket:** N/A
**Related plan:** [skill-docs-progressive-disclosure-progress-tracker-improvement-plan.md](../_plans/skill-docs-progressive-disclosure-progress-tracker-improvement-plan.md)
**Created:** 2026-07-28
**Updated:** 2026-07-28

---

## Scope

| Scope | Branch | Ticket | Notes |
|---|---|---|---|
| `progress-tracker` | TBD | TBD |  |

## Background & goals

Execute the user-supplied `progress-tracker-improvement-plan.md` (per the
writing-great-skills review of `SKILL.md`): reduce context load, eliminate
duplication between `SKILL.md` and `references/workflow.md`, and strengthen
leading-word anchoring — using the repo's own evals (trigger matrix +
scenarios) and `scripts/verify.sh` as the regression net throughout. Expected
outcome: `SKILL.md` shrinks well below its 302-line starting point without
losing any enforced behavior, and the migration contract lives in exactly one
authoritative place.

## Task list

- [x] Phase 1 — split the migration contract into `references/migration.md`; prune no-op sentences
- [x] Phase 2 — rewrite the frontmatter description; record invocation-semantics decision
- [x] Phase 3 — anchor migration as a two-phase commit; negation scan
- [x] Phase 4 — shared vocabulary, editing checklist, eval-tautology audit, plugin version bump
- [x] Interface-design experiment — defer argument semantics to `--help` via a coverage matrix
- [x] Close the scope-comma silent-failure trap the experiment surfaced (ambiguity + empty-entry errors, scope echo)
- [x] Address PR #1 code review (explicit-empty-`--scope` handling, review-status honesty, plan deviation record)

## Work log

### 2026-07-28

- Phase 1: split migration contract into references/migration.md (single authoritative doc, absorbing workflow.md's parallel section), pruned SKILL.md 302 -> 195 lines, synced doc surfaces; verify.sh green.
- Phase 2: rewrote frontmatter description (one leading trigger per lifecycle branch, preflight anchor, 110 words) and recorded the single-skill invocation-semantics decision; SKILL.md at 178 lines.
- Phase 3: anchored the two-phase-commit leading sentence above the gate block (outside the byte-synced markers) and in migration.md's opening; negation scan kept hard guardrails, soft negations were already rewritten positively during the split.
- Phase 4: shared vocabulary in domain-models.md, SKILL.md editing checklist in AGENTS.md, eval-tautology audit recorded, plugin manifests bumped to 1.8.0; full gate green. Branch ready for review.
- Closed item as `done`.
- Reopened to `review` per PR #1 code review: an item is not `done` while its PR is
  still open. Also addressed the review findings (scope-comma guard: explicit empty
  `--scope` now rejected instead of silently ignored; `--help` names leading commas;
  plan deviations recorded).

## Outcome

Executed the writing-great-skills refactor: SKILL.md 302 -> 180 lines via progressive disclosure into references/migration.md (single authoritative migration doc), description rewritten with one trigger per lifecycle branch, two-phase-commit leading anchor added, shared vocabulary + SKILL.md editing checklist + eval-tautology audit recorded; plugin 1.8.0. verify.sh, ruff, 14 scenarios, and grader regression all green.

**Final status:** review — [PR #1](https://github.com/FWcloud916/skill-progress-tracker/pull/1) open; close as `done` after merge
**PR / Commit:** [PR #1](https://github.com/FWcloud916/skill-progress-tracker/pull/1) (branch claude/progress-tracker-improvement-plan-950330)
**Follow-ups:** None
