# progress-tracker — Agent Guide

An agent skill that tracks local development progress across single- or
multi-scope tasks for any project. The canonical skill lives in
`skills/progress-tracker/` (SKILL.md + references/ + scripts/); the repo
doubles as a Claude Code plugin (`.claude-plugin/`) and a native Codex plugin
with a repo marketplace (`.codex-plugin/` + `.agents/plugins/`).

## Hard constraints

- MUST run `bash scripts/verify.sh` and see it pass before declaring any change done (source: this repo's verification gate)
- MUST keep `new_progress.py`'s substituted placeholder set in exact sync with `references/PROGRESS.template.md`, and keep `TABLE_HEADER_MARKER` identical to `references/INDEX.template.md`'s header row (source: scripts/verify.sh)
- MUST keep the status enum (`planning`, `in-progress`, `review`, `blocked`,
  `done`, `abandoned`) and its transition diagram identical across
  `SKILL.md`, `references/workflow.md`, and `references/INDEX.template.md`
  (source: scripts/verify.sh)
- MUST keep `update_progress.py`'s migration placeholders, table header, marker constants, `HUMAN_SIGNOFF_ITEMS`, and `DISPOSITION_VALUES` in exact sync with `references/MIGRATION.template.md` (source: scripts/verify.sh)
- MUST keep the `<!-- MIGRATION_GATE_START/END -->` command-sequence block
  byte-identical across `SKILL.md`, `references/workflow.md`, and
  `agents/progress-tracker.md` (source: scripts/verify.sh)
- MUST NOT let the migration gate open short of clean reconciliation: unknown headings default to blocking, historical entries remain preserved, migrated rows need unique Evidence, and retain/delete outcomes use non-destructive finalization (source: KNOWN-ISSUE.md KI-001/KI-002, docs/design-decisions.md)
- MUST preserve generic input semantics: tickets remain verbatim, scopes remain free-form labels without directory validation, and bare plan names resolve only through `$PROGRESS_TRACKER_PLANS_DIR` (source: docs/design-decisions.md)
- MUST update matching scenario and grader assertions whenever a CLI flag, output file, or file-scope behavior changes (source: evals/README.md)
- Changes to `new_progress.py` or `update_progress.py` behavior MUST include matching updates to their adjacent pytest files (source: docs/design-decisions.md)
- MUST edit `AGENTS.md`, never the `CLAUDE.md` symlink (source: repository symlink policy)
- User-visible skill changes MUST bump the identical versions in both plugin manifests; the Codex marketplace source MUST remain `./` with `AVAILABLE`, `ON_INSTALL`, and `Productivity` policy (source: plugin manifests, .agents/plugins/marketplace.json, docs/design-decisions.md)
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
| Architecture, interfaces, directory layout, packaging, or environments | [docs/project-overview.md](docs/project-overview.md) |
| Progress-item, status, audit, or migration domain behavior | [docs/domain-models.md](docs/domain-models.md) |
| Python style, lint rules, validation patterns, or architecture boundaries | [docs/coding-style.md](docs/coding-style.md) |
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
uv run --python 3.14 --with pytest python3 -m pytest skills/progress-tracker/scripts/ -v  # unit + integration tests for both lifecycle scripts
./evals/scripts/run_scenarios.sh                                                 # end-to-end lifecycle scenarios
python3 evals/scripts/test_grade_scenarios.py                                    # free scenario-grader regression tests
```

## Conventions

- Enhance over rewrite: extend existing tables/sections; restructure only
  when scale justifies it.
- Requirement keywords (MUST/SHOULD/MAY) follow RFC 2119, uppercase.
- English throughout — templates, field names, and section headings.

## Docs maintenance

When modifying any file under `docs/`, update its `> **Last updated:**
YYYY-MM-DD` frontmatter to today's date.
