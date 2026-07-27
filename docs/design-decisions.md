# Design decisions

> **Type:** Reference
> **Audience:** Maintainers, AI agents
> **Last updated:** 2026-07-27

A decision log with rationale, in chronological order. When a design choice
seems arbitrary, check here before changing it.

---

## 2026-07-24 — Add a separate lifecycle mutation and audit script

`new_progress.py` remains a backward-compatible creation command. Update,
close-out, and consistency checking live in `update_progress.py` instead of
turning the established positional create CLI into a subcommand interface.
This follows the repository's enhance-over-rewrite convention while removing
the riskiest manual step: editing status independently in `PROGRESS.md` and
`INDEX.md`.

The lifecycle script discovers items by their stable `**Slug:**` field,
requires exactly one matching item and INDEX row, rejects existing drift,
validates transitions before writing, and provides dry-run diffs. Its `check`
command audits invalid statuses, duplicate slugs/rows, missing rows, stale
rows, and status drift. Writes are validation-atomic and use best-effort
rollback for ordinary filesystem errors; they are not a cross-file
transaction against process or machine crashes.

Allowed transitions reflect normal review rework and explicit termination:
`planning → in-progress`, `in-progress ⇄ review`,
`in-progress ⇄ blocked`, and any non-terminal status → `abandoned`.

## 2026-07-24 — Escape scope delimiters and Markdown table values

Scope labels remain free-form and filesystem-independent. The compact legacy
syntax stays compatible, with backslash escaping added for literal commas,
colons, and backslashes. The first two unescaped colons delimit fields and an
unescaped comma delimits scope entries.

All CLI values written into Markdown tables are now rendered through shared
helpers. Pipes and backslashes are escaped, code spans choose a delimiter that
can contain literal backticks, and embedded newlines are rejected. Ticket
values remain semantically verbatim: the script still does not normalize or
invent tracker syntax; Markdown escaping only protects the output structure.

## 2026-07-24 — Namespace plan snapshots by task slug

The original basename-only `_plans/<plan-name>` layout made common names such
as `plan.md` collide across unrelated tasks. Snapshots now use
`_plans/<slug>-<plan-name>` and are rendered as explicit URL-encoded relative
Markdown links. Existing tracker records remain readable because the lifecycle
script follows the paths already recorded in each item and does not migrate or
rename historical snapshots.

## 2026-07-24 — Support Python 3.10 as the real language floor

The scripts use Python 3.10 syntax (`X | None`) but no Python 3.14-only
language or standard-library behavior. Requiring 3.14 forced unnecessary
runtime downloads and weakened offline portability. PEP 723 metadata now
declares Python 3.10+, and CI exercises both 3.10 and 3.14 so the documented
minimum and current runtime remain proven.

## 2026-07-24 — Pin ruff's version in CI after a false-green local check

The first CI run failed `ruff check .` with 23 errors (deprecated `typing.List`/
`Optional`/`Tuple` usage, a naive `date.today()` call, `subprocess.run` without
an explicit `check=`), even though a local `ruff check .` run reported "All
checks passed!" immediately beforehand. Root cause: the locally installed
`ruff` binary was an older version (0.15.4) than the one CI's
`uv tool install ruff` resolved at run time (0.16.0), and ruff had changed
which rule families are enabled by default between those versions. Same repo,
same command, different result — purely from an unpinned tool version.

Fix: pin an exact ruff version in `.github/workflows/ci.yml`
(`uv tool install ruff==0.16.0`) instead of "latest", and record here that
local verification MUST use the same pinned version (`uvx ruff==0.16.0 check .`)
— never trust a `ruff` binary that happens to already be on `PATH` locally,
since its version (and therefore its default rule set) isn't guaranteed to
match CI's.

## 2026-07-24 — Extracted from Kdan Mobile's `progress-note` skill

`progress-tracker` generalizes Kdan Mobile's internal `kdan-workflow` repo's
`progress-note` skill into a standalone, project-agnostic skill — the same
treatment `project-docs` (Kdan) received when it was generalized into
`doc-architect`. The relationship to the Kdan-internal skill is a **sibling
cross-reference, not a wrapper**: `progress-note` keeps its workspace-specific
behavior untouched; `progress-tracker` has no dependency on it.

### What was genericized, and why

| Kdan-specific behavior | Generic replacement | Why |
|---|---|---|
| `--services name` validated as a directory under a fixed workspace root | `--scope name` — free-form label, no filesystem validation | The workspace-root/sibling-directory assumption doesn't hold for an arbitrary project; a scope is just a label for a piece of work |
| Redmine `#`-digit ticket normalization | Tickets kept **verbatim** | Baking in one tracker's numbering convention (Redmine serials) would misrepresent Jira keys, GitHub issue URLs, or anything else |
| Bare-filename plan resolution defaulting to `~/.claude/plans` then a `ticket-sync` state directory | Bare filename resolved only via the explicit `$PROGRESS_TRACKER_PLANS_DIR` env var; otherwise the caller must pass a path | Hardcoding one tool's output directory as a default silently couples this skill to that tool's install; an explicit opt-in env var keeps the convenience without the coupling |
| Self-location via a workspace symlink trick (`__file__.absolute()` → a `WORKSPACE_ROOT` a sibling `config.env` defines) | Project root = `--root` > `git rev-parse --show-toplevel` > cwd | No generic project has this repo's symlink layout; git-toplevel detection is the standard convention-over-configuration answer |
| Cross-references to `ticket-sync`, `finish-ticket`, `/finish-ticket` | Removed entirely | Those are Kdan-workflow-internal skills; a generic skill must be usable with zero other skills installed |
| Chinese field/section names and the exact Chinese `INDEX.md` header-marker string | English throughout | The generic skill targets any project/team, not a Traditional-Chinese-speaking one |

### Deliberately kept

- **Multi-scope tracking.** The user explicitly wanted to preserve
  cross-scope task tracking (the most distinctive feature versus a plain
  single-project worklog) — just de-Kdan'd. A single-scope project is simply
  one `--scope` entry.
- **The plan-snapshot mechanism** (`--plan` copies a plan file into a
  version-controlled `_plans/` directory). The rationale carries over
  unchanged: planning-tool output locations vary and aren't always
  redirectable, so copying is the only thing that converges every source
  into version control.
- **The status enum and its shape** (`planning → in-progress → review →
  done`, with `blocked`/`abandoned` branches) — unchanged from the source
  skill; it's already generic.

---

## Script-first evaluation strategy (vs. doc-architect's model-graded detection)

`doc-architect`'s hardest problem — stack detection — is executed by a model
and can only be graded by running that model against fixture repos and
diffing its report against ground truth. `progress-tracker`'s core is
different: `new_progress.py` is a deterministic script. Its correctness is
provable with ordinary unit tests, no model call required.

Consequences:
- `skills/progress-tracker/scripts/test_new_progress.py` (pytest) is the
  **primary** correctness gate — not a secondary check. It runs free, in
  milliseconds, on every `verify.sh` invocation and every CI run.
- `evals/` still exists, but scoped down to what pytest genuinely can't
  cover: end-to-end lifecycle behavior through disposable-repo scenarios
  (mirroring doc-architect's `evals/scenarios/` shape) and a trigger-matrix
  contract for when an agent should (or shouldn't) reach for this skill. It
  does **not** need doc-architect's large fixture-based detection suite,
  because there is no detection step to test.
- CI can run the full test suite on every push/PR for free (no
  `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` spend), unlike doc-architect's
  detection sweep, which is manual-trigger-only because each run costs a
  model call.

## Tracker directory naming

Defaults to `progress/` at the project root (matching the Kdan predecessor's
`progress_note/` in spirit, shortened since the generic skill has no
workspace-level "note" concept to disambiguate from). Configurable via
`--dir` or `$PROGRESS_TRACKER_DIR` for projects that already use that name
for something else, or prefer a dotfile (`.progress/`).

## Portable script invocation

Skill instructions refer to the scaffold script as
`<skill-dir>/scripts/new_progress.py`, where `<skill-dir>` is the directory
containing the installed skill's `SKILL.md`. A project cannot use a bare
`new_progress.py` command because the script is bundled with the skill, not
copied into every tracked project; runtime-specific environment variables
would also undermine the skill's cross-agent portability.

## Project-contained tracker paths

`--dir` and `$PROGRESS_TRACKER_DIR` accept hidden or nested relative paths,
but the resolved tracker path must be a strict descendant of the project
root. Absolute paths, the root itself, parent traversal, and symlink escapes
are rejected. This keeps an agent's tracker writes inside the project it was
asked to operate on while preserving useful layouts such as `.progress/` and
`docs/progress/`.

## Validation-atomic item creation

The scaffold script validates all predictable failure conditions before it
writes anything: item-folder collisions, plan source/destination validity,
bundled seed availability, output-path containment, template rendering, and
the INDEX insertion marker. This guarantees that a validation error cannot
leave an orphan `PROGRESS.md`, plan snapshot, or INDEX row. It is not a
multi-file transaction against process crashes or storage failures.

## 2026-07-26 — Require consent and a pointer audit before legacy-tracker migration

Projects may already use a root `PROGRESS.md`, a differently named tracking
directory, or instructions that point agents to another state file. Silently
scaffolding `progress/` in that situation creates competing sources of truth,
as the real-world trial against `FWcloud916.github.io` demonstrated.

Existing-tracker discovery therefore lives in the agent workflow before the
deterministic scaffold command. Artifact names and migration mappings vary too
widely for `new_progress.py` to guess safely. When a separate mechanism is
found, the agent must inventory it and its pointers, obtain explicit migration
or coexistence consent, and preserve the source unless removal is separately
approved.

Migration completion has two independent gates. First, copy all in-progress
state while keeping the source unchanged, then compare every active source
field with its destination and explain canonical status/field mappings. Second,
run the tracker consistency check, search the project for every old path/name,
inspect changed relative links, and classify any remaining occurrence as
intentionally historical or compatibility-related. Missing active content, a
semantic mismatch, or an unreviewed stale pointer means migration is
incomplete.

Only after both gates pass does the agent ask whether to delete the original
tracking artifacts. Approval must identify the exact legacy target. Deletion
is followed by the same consistency and pointer/link audits; declining keeps
the source as a legacy record while live pointers remain on the new tracker.

## 2026-07-26 — Script-gate migration inventory completeness (KI-001)

The migration contract above turned out to be insufficient in practice: see
`KNOWN-ISSUE.md` KI-001. A real migration trial against
`FWcloud916.github.io` had a legacy `PROGRESS.md` whose `## Now` section said
"Nothing in progress." The agent treated the active-content set as empty,
reported that its content and pointer audits passed, and reached the deletion
prompt — while `## Next steps` and an SEO/AI-SEO backlog it never inspected
still held real, unmigrated work. The root cause was structural, not a
one-off slip: the "audit" only compared fields already selected for mapping;
nothing proved the source inventory itself was complete. And the entire
contract was prose an agent follows, with no script checking it — so a
passing `update_progress.py check` (tracker-internal consistency only)
created false confidence about something it never looked at.

The fix is two new `update_progress.py` subcommands, not more emphatic prose:

- `migration-inventory <slug> --source <path>` scans a legacy source
  **whole-document** and writes a reconciliation record to
  `<tracker-dir>/_migrations/<slug>.md`. If this is first adoption, it
  scaffolds the tracker support files without creating an item, preserving the
  contract that inventory precedes destination creation. Every section is classified
  `actionable`, `historical`, or — for anything neither keyword list
  recognizes — `ambiguous`, which blocks exactly like `actionable`. This is
  the direct fix: a heading nobody thought to add to a keyword list defaults
  to blocking, not to being silently treated as already covered. An
  unchecked `- [ ]` or inline `TODO`/`TBD` marker is actionable regardless of
  its section, including inside a `## Done` heading. Prose blocks, list items,
  and complete table rows are emitted in source order; a section containing a
  list no longer suppresses adjacent prose, and table rows retain every
  header/value pair instead of only their first cell.
- `migration-audit <slug>` rescans the source and reconciles it against the
  record. It is the pre-deletion gate: it fails while any `actionable`/`ambiguous`
  entry lacks a valid `migrated`/`excluded` Disposition and Destination, any
  generated row field was hand-edited, any `migrated` Destination isn't an
  existing tracker item slug, its Evidence does not occur uniquely in that
  item, the source changed since the inventory was
  taken, or a pre-deletion human sign-off box (semantic equivalence, pointer
  audit, link audit, historical disclosure) is unticked. Refreshing a changed
  source or generated inventory resets all global sign-offs; they survive only
  an identical inventory.

Schema v2 strengthens destination verification: every `migrated` row carries
a non-trivial Evidence locator copied from its destination item, and audit
requires that locator to occur exactly once. Semantic equivalence and external
pointer/link correctness remain human-attested because the script cannot infer
intent from matching text alone.

**Deliberately conservative `HISTORICAL_HEADINGS`:** every entry in that list
is a suppression vector — a heading that should have blocked but silently
didn't is exactly what KI-001 was. `ACTIONABLE_HEADINGS` can be generous
because a false positive there only adds a row someone has to disposition;
`HISTORICAL_HEADINGS` stays narrow because a false positive there reproduces
the incident. Anything on neither list falls through to `ambiguous`, which
  blocks — so an incomplete list is safe by construction, never silently lossy.

The deletion decision remains after `migration-audit`, but it is no longer
conversation-only. `migration-finalize` records `pending → retained` or
`pending → delete-approved → deleted`. Delete approval reruns the audit and
seals the exact source set plus a SHA-256 fingerprint of rows and sign-offs;
the script never deletes sources. Confirmation requires every approved source
to be absent, the seal to remain unchanged, and tracker consistency to pass.

Entry-level `archived` was removed as well. Retaining a legacy source is one
document-level user choice, not a row disposition. Blocking rows accept only
`migrated` or reasoned `excluded`; non-blocking rows seed `not-applicable` and
historical/reference sections are disclosed before the user makes the later
document-level retention decision.

## 2026-07-27 — Preserve full migration evidence and outcome (KI-002)

A real-project retry showed that the KI-001 gate still compressed each
historical section to its heading, accepted a destination slug without a
per-entry locator, and left the final retain/delete answer only in chat.
Schema v2 therefore inventories every historical entry, adds uniquely matching
destination Evidence to each migrated row, and stores a durable non-destructive
outcome state. Existing schema v1 records refresh to v2: compatible
Disposition/Destination choices survive, migrated Evidence starts unresolved,
and global sign-offs reset because the evidence basis changed.

## 2026-07-26 — Standardize on a single supported Python version (3.14)

Supersedes the dual-version part of "2026-07-24 — Support Python 3.10 as the
real language floor". The maintainer chose to keep exactly one supported
Python version instead of a 3.10 floor plus a 3.10/3.14 CI matrix. 3.14 is
the newest stable release (3.15 is not released as of this writing), so
`requires-python = ">=3.14"` in both scripts' PEP 723 metadata, a single
CI job on 3.14, and a `verify.sh` check that all of these declarations name
the same version.

The trigger was a real gate failure: on a stock macOS machine, `verify.sh`'s
end-to-end scenario check failed 9/9 because `run_scenarios.py` executed the
scripts under test with `sys.executable` — the system `python3` (3.9.6) that
had launched the harness — ignoring the scripts' declared floor entirely.
`new_progress.py`'s `str | None` annotations then raised a def-time
`TypeError` (it lacked the `from __future__ import annotations` its sibling
`update_progress.py` already had). CI stayed green because ubuntu runners
satisfied the floor — the same environment-drift trap as the 2026-07-24 ruff
incident, in the opposite direction.

Fixes, in order of importance:
1. `run_scenarios.py` now executes the scripts under test with
   `uv run --quiet`, which reads PEP 723 and provisions the declared Python;
   without uv it falls back to the current interpreter only when that
   interpreter satisfies the floor, and exits with a clear error otherwise.
   The scenario harness itself (like the grader) stays runnable on any
   modern system `python3`.
2. `new_progress.py` gained `from __future__ import annotations` for parity
   with `update_progress.py` — defense in depth so a bare `python3` run on an
   old interpreter reaches argparse and real error messages instead of a
   def-time `TypeError`.
3. `verify.sh` pins the pytest step to `--python 3.14` and asserts the
   version declarations agree across both scripts and CI, so a future bump
   must change them together.
