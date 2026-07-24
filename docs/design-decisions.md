# Design decisions

> **Type:** Reference
> **Audience:** Maintainers, AI agents
> **Last updated:** 2026-07-24

A decision log with rationale, in chronological order. When a design choice
seems arbitrary, check here before changing it.

---

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
