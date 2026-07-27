# progress-tracker — Agent Guide

An agent skill that tracks local development progress across single- or
multi-scope tasks for any project. The canonical skill lives in
`skills/progress-tracker/` (SKILL.md + references/ + scripts/); the repo
doubles as a Claude Code plugin (`.claude-plugin/`) and a native Codex plugin
with a repo marketplace (`.codex-plugin/` + `.agents/plugins/`).

## Hard constraints

- MUST run `bash scripts/verify.sh` and see it pass before declaring any
  change done (source: this repo's verification gate)
- MUST keep the placeholder set `new_progress.py` substitutes (`{{TITLE}}`,
  `{{SLUG}}`, `{{SCOPE_ROWS}}`, `{{TICKET}}`, `{{PLAN}}`, `{{DATE}}`) in exact
  sync with `references/PROGRESS.template.md`'s placeholders — adding or
  renaming one requires updating both (source: scripts/verify.sh)
- MUST keep `new_progress.py`'s `TABLE_HEADER_MARKER` string identical to
  `references/INDEX.template.md`'s header row — the script locates the
  insertion point by exact string match (source: scripts/verify.sh)
- MUST keep the status enum (`planning`, `in-progress`, `review`, `blocked`,
  `done`, `abandoned`) and its transition diagram identical across
  `SKILL.md`, `references/workflow.md`, and `references/INDEX.template.md`
  (source: scripts/verify.sh)
- MUST keep `update_progress.py`'s migration `{{X}}` placeholder set in exact
  sync with `references/MIGRATION.template.md`, and its `MIGRATION_TABLE_HEADER` /
  `MIGRATION_*_START`/`_END` marker constants identical to the template's
  header row and markers (source: scripts/verify.sh)
- MUST keep `update_progress.py`'s `HUMAN_SIGNOFF_ITEMS` and
  `DISPOSITION_VALUES` in exact sync with `references/MIGRATION.template.md`'s
  sign-off checklist labels and Disposition table — `migration-audit` greps
  these labels at runtime, so drift here breaks the gate silently
  (source: scripts/verify.sh)
- MUST keep the `<!-- MIGRATION_GATE_START/END -->` command-sequence block
  byte-identical across `SKILL.md`, `references/workflow.md`, and
  `agents/progress-tracker.md` (source: scripts/verify.sh)
- MUST NOT let `migration-audit`'s pre-deletion gate open on anything short of a
  clean reconciliation — an unrecognized source heading MUST default to
  blocking (`ambiguous`), never to being silently treated as already covered
  (source: KNOWN-ISSUE.md KI-001, docs/design-decisions.md)
- MUST preserve every historical migration entry, require uniquely matching
  Evidence for every `migrated` row, and persist retain/delete outcomes via
  the non-destructive `migration-finalize` state machine
  (source: KNOWN-ISSUE.md KI-002, docs/design-decisions.md)
- MUST NOT reintroduce ticket normalization (`#`-prefixing digits, or any
  other tracker-specific reformatting) — tickets are kept verbatim by design
  (source: docs/design-decisions.md)
- MUST NOT reintroduce directory validation for `--scope` entries — scope
  names are free-form labels, not validated against any filesystem path
  (source: docs/design-decisions.md)
- MUST NOT hardcode a specific tool's plan-output path (e.g. `~/.claude/plans`)
  as a default lookup location — bare-filename plan resolution only happens
  via the explicit `$PROGRESS_TRACKER_PLANS_DIR` env var (source: docs/design-decisions.md)
- MUST update `evals/scenarios/*/scenario.json` (and its grader assertions)
  in the same change whenever a CLI flag, output file, or file-scope
  behavior changes (source: evals/README.md)
- Changing `new_progress.py`'s behavior MUST come with matching updates to
  `skills/progress-tracker/scripts/test_new_progress.py` in the same change —
  this test suite is the primary correctness gate, since (unlike
  doc-architect's model-graded detection) this skill's core logic is
  deterministic and testable (source: docs/design-decisions.md)
- Changing `update_progress.py`'s behavior MUST come with matching updates to
  `skills/progress-tracker/scripts/test_update_progress.py` in the same change;
  lifecycle mutations and audits are deterministic and MUST remain covered
  (source: docs/design-decisions.md)
- MUST edit `AGENTS.md`, never `CLAUDE.md` (symlink)
- User-visible skill changes MUST bump `version` in both
  `.claude-plugin/plugin.json` and
  `.codex-plugin/plugin.json`, keeping them identical
  — plugin users only receive updates on a version bump (source: plugins reference)
- MUST keep `.agents/plugins/marketplace.json`'s `progress-tracker` source at
  `./`, with explicit `AVAILABLE` installation,
  `ON_INSTALL` authentication, and `Productivity` category policy
- MUST lint with the exact ruff version pinned in `.github/workflows/ci.yml`
  (`uvx ruff==<pinned version> check .`), not a locally installed `ruff`
  binary — a stale local install can silently under-report (ruff has changed
  its default rule set across versions before; a local pass is not proof CI
  will pass) (source: 2026-07-24 CI failure, see docs/design-decisions.md)

## Read before you work

Read the matching doc **before non-trivial work**. Small fixes (typos,
single-line edits) can skip; do not pre-load all docs.

| Task | Read first |
|---|---|
| Changing scaffold-script behavior or CLI arguments | [SKILL.md](skills/progress-tracker/SKILL.md) + [new_progress.py](skills/progress-tracker/scripts/new_progress.py) |
| Changing lifecycle update, close-out, or audit behavior | [SKILL.md](skills/progress-tracker/SKILL.md) + [update_progress.py](skills/progress-tracker/scripts/update_progress.py) |
| Changing the item template or INDEX shape | [PROGRESS.template.md](skills/progress-tracker/references/PROGRESS.template.md) + [INDEX.template.md](skills/progress-tracker/references/INDEX.template.md) |
| Changing the status lifecycle | [SKILL.md](skills/progress-tracker/SKILL.md) §Status lifecycle + [workflow.md](skills/progress-tracker/references/workflow.md) |
| Changing migration-inventory/migration-audit behavior or the record shape | [SKILL.md](skills/progress-tracker/SKILL.md) §Before creating anything + [MIGRATION.template.md](skills/progress-tracker/references/MIGRATION.template.md) + [KNOWN-ISSUE.md](KNOWN-ISSUE.md) KI-001 |
| Changing eval scenarios or the trigger matrix | [evals/README.md](evals/README.md) |
| Changing Codex plugin packaging or installation | [README.md](README.md) §Install + [docs/design-decisions.md](docs/design-decisions.md) Codex packaging decision |
| Understanding why it's built this way | [docs/design-decisions.md](docs/design-decisions.md) |

## Commands

```bash
bash scripts/verify.sh                                                          # consistency gate — the verification gate for "done"
uv run --python 3.14 --with pytest python3 -m pytest skills/progress-tracker/scripts/ -v  # unit + integration tests for the scaffold script
./evals/scripts/run_scenarios.sh                                                 # end-to-end lifecycle scenarios
python3 evals/scripts/test_grade_scenarios.py                                    # free scenario-grader regression tests
```

## Conventions

- Enhance over rewrite: extend existing tables/sections; restructure only
  when scale justifies it.
- Requirement keywords (MUST/SHOULD/MAY) follow RFC 2119, uppercase.
- English throughout — templates, field names, section headings. (This skill
  is the generic, workspace-independent sibling of Kdan Mobile's internal
  `progress-note` skill, which stays in Traditional Chinese for that
  workspace.)

## Docs maintenance

When modifying any file under `docs/`, update its `> **Last updated:**
YYYY-MM-DD` frontmatter to today's date.
