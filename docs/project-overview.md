# progress-tracker — Project Overview

> **Type:** Explanation
> **Audience:** Developers, AI assistants, and tooling that needs project context
> **Last updated:** 2026-07-28
>
> A reusable agent skill and deterministic CLI toolkit for durable, local development-progress tracking. Related docs: [domain-models.md](domain-models.md), [coding-style.md](coding-style.md), and [design-decisions.md](design-decisions.md).

---

## 1. Purpose

`progress-tracker` gives developers and AI agents a version-controlled record of work
that spans an investigation-to-merge lifecycle. It supports a single free-form scope or
several scopes without assuming a particular issue tracker, repository layout, or agent
runtime.

### 1.1 Core Responsibilities

- Scaffold a project-local tracker and dated progress items from canonical Markdown
  templates.
- Keep each item's status synchronized with the tracker index while work is updated or
  closed.
- Audit tracker structure for invalid states, duplicate identities, missing rows, stale
  rows, and status drift.
- Inventory and reconcile legacy tracking documents before any deletion decision.
- Package the same canonical skill for Claude Code, Codex, direct skill installation,
  and manual symlink installation.

The public behavior is specified in
[`skills/progress-tracker/SKILL.md`](../skills/progress-tracker/SKILL.md). The longer
operational rationale and field reference live in
[`workflow.md`](../skills/progress-tracker/references/workflow.md).

### 1.2 Relationship with Other Systems

The installed skill operates on a target project's local filesystem. It discovers that
project's root from `--root`, the Git top level, or the current working directory, then
writes only inside a configured tracker directory. Git is used for root discovery and
for versioning the generated records; the scripts do not call a ticketing or hosting
API.

The repository is also a plugin distribution root:

- [`.claude-plugin/plugin.json`](../.claude-plugin/plugin.json) describes the Claude
  Code plugin.
- [`.codex-plugin/plugin.json`](../.codex-plugin/plugin.json) points Codex at the
  canonical `skills/` directory.
- [`.agents/plugins/marketplace.json`](../.agents/plugins/marketplace.json) publishes
  the local Codex marketplace entry.
- [`agents/progress-tracker.md`](../agents/progress-tracker.md) provides the dedicated
  Claude Code agent definition.

### 1.3 Deprecated / Retired or Not-Yet-Enabled Features

- **Migration schema v1 is upgrade-only.** `migration-inventory` can read a v1 record
  and refresh it to schema v2, but finalization requires schema v2.
- **Python 3.10 support is retired.** The later 2026-07-26 design decision supersedes
  the earlier 3.10-floor decision; both executable scripts and CI require Python 3.14.
- **Automatic cleanup is intentionally not enabled.** Current item folders and index
  rows remain human-managed. Migration finalization records approval and verifies
  deletion, but never deletes a legacy source itself.

## 2. Tech Stack

The stack detector has no supported root manifest to match, so its formal resolution is
`unknown`. The implementation is nevertheless explicit in the repository:

| Concern | Technology | Evidence and role |
|---|---|---|
| Skill specification and generated records | Markdown | [`SKILL.md`](../skills/progress-tracker/SKILL.md) and [`references/`](../skills/progress-tracker/references/) |
| Deterministic CLIs | Python 3.14+, standard library only | PEP 723 metadata in [`new_progress.py`](../skills/progress-tracker/scripts/new_progress.py) and [`update_progress.py`](../skills/progress-tracker/scripts/update_progress.py) |
| Script runner | `uv` | Resolves the PEP 723 runtime for direct use, tests, and scenarios |
| Repository verification | Bash + Python | [`scripts/verify.sh`](../scripts/verify.sh) |
| Unit and integration tests | pytest | `test_new_progress.py` and `test_update_progress.py` beside the scripts under test |
| End-to-end evaluation | Python + JSON scenarios | [`evals/`](../evals/) |
| Linting | Ruff 0.16.0 | Pinned in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) |
| Continuous integration | GitHub Actions | Python tests, Ruff, then the consistency gate on pushes and pull requests |
| Distribution | Claude Code and Codex plugin manifests | `.claude-plugin/`, `.codex-plugin/`, and `.agents/plugins/` |

There is no dependency lockfile because the runtime scripts declare no third-party
dependencies. pytest and Ruff are provisioned by verification or CI commands rather
than installed as runtime dependencies.

## 3. Architecture Overview

The repository separates human/agent workflow guidance from deterministic mutations:

```text
User or agent request
        |
        v
skills/progress-tracker/SKILL.md --------> references/workflow.md + migration.md
        |                                          |
        | chooses command                          | explains fields and policy
        v                                          v
new_progress.py or update_progress.py ------> Markdown templates
        |
        | validates inputs, paths, and current state
        v
Target project's tracker directory
```

`new_progress.py` owns first-use scaffolding and item creation.
`update_progress.py` imports its shared parsing, rendering, and containment helpers, then
adds lifecycle mutation, tracker audits, legacy-source scanning, reconciliation, and
migration finalization. The verification script protects constants and prose blocks
that must remain byte- or value-identical across Python and Markdown sources.

### Key Principles

- **One canonical skill payload.** `skills/progress-tracker/` is shared by all
  packaging routes; generated copies are not maintained.
- **Validate before mutation.** Creation resolves templates, output paths, collisions,
  and the index insertion point before writing any file.
- **Keep coupled state together.** Lifecycle mutations validate and update an item's
  `PROGRESS.md` and `INDEX.md` status as one operation with best-effort rollback on
  ordinary write errors.
- **Contain writes.** Tracker and scaffold targets must resolve strictly below the
  selected project root; scope labels remain free-form and are never treated as paths.
- **Fail closed on migration ambiguity.** Unrecognized source headings are blocking,
  every migrated row needs unique destination evidence, and source outcomes are
  persisted through a non-destructive state machine.
- **Test deterministic behavior deterministically.** pytest and disposable-repository
  scenarios exercise filesystem and content invariants without an LLM judge.

## 4. Directory Structure

```text
progress-tracker/
├── .agents/plugins/              # Codex marketplace catalog
├── .claude-plugin/               # Claude Code plugin and marketplace manifests
├── .codex-plugin/                # Native Codex plugin manifest
├── .github/workflows/ci.yml      # CI runtime, test, lint, and consistency gates
├── agents/progress-tracker.md    # Dedicated Claude Code agent definition
├── docs/                         # Maintainer-facing architecture and rationale
├── evals/
│   ├── scenarios/                # Disposable-repository lifecycle fixtures
│   ├── scripts/                  # Scenario runner, grader, and grader tests
│   └── trigger-matrix.json       # Skill trigger-boundary contract
├── progress/                     # This repository's own development-work history
├── scripts/verify.sh             # Mandatory repository consistency gate
└── skills/progress-tracker/
    ├── SKILL.md                  # Canonical agent workflow and public command contract
    ├── agents/openai.yaml        # Codex skill UI metadata
    ├── references/               # Workflow, migration contract, templates, and seed docs
    └── scripts/
        ├── new_progress.py       # Scaffold and create CLI
        ├── update_progress.py    # Update, close, audit, and migration CLI
        ├── test_new_progress.py  # Creation unit/integration tests
        └── test_update_progress.py # Lifecycle and migration unit/integration tests
```

`CLAUDE.md` is a symlink to the root [`AGENTS.md`](../AGENTS.md); maintainers edit the
canonical file, never the symlink.

## 5. Domain Models (High-Level)

The project has no database-backed models. Its domain entities are Markdown records and
their parsed in-memory representations:

```text
Project root 1──1 Tracker directory
Tracker directory 1──* Progress item
Tracker directory 1──1 Index
Progress item 0──1 Plan snapshot
Migration record *──* Legacy source
Migration record *──* Progress item (through Destination + Evidence)
```

- A **progress item** has a stable slug, lifecycle status, umbrella ticket, optional
  frozen plan link, scope rows, task list, work log, and outcome.
- The **index** contains one row per progress item and mirrors each item's status.
- A **migration record** inventories legacy-source entries, records their disposition
  and destination evidence, stores human sign-offs, and persists the source-level
  retain/delete outcome.
- A **plan snapshot** is immutable original intent; the progress item is the living
  record of work actually performed.

See [domain-models.md](domain-models.md) for field rules, lifecycle transitions, and
migration reconciliation behavior.

## 6. API / Interface Structure

The project exposes command-line interfaces rather than an HTTP API.

| Entrypoint | Command | Purpose | Mutates files |
|---|---|---|---|
| `new_progress.py` | `<slug> --scope ...` | Scaffold support files, create an item, optionally snapshot a plan, append an index row | Yes, unless `--dry-run` |
| `update_progress.py` | `update <slug>` | Replace scope rows, complete exact tasks, append work log entries, and transition active status | Yes, unless `--dry-run` |
| `update_progress.py` | `close <slug>` | Fill the outcome and close as `done` or `abandoned` | Yes, unless `--dry-run` |
| `update_progress.py` | `check` | Audit item/index consistency | No |
| `update_progress.py` | `migration-inventory <slug>` | Scan legacy Markdown sources and create or refresh a reconciliation record | Yes, unless `--dry-run` |
| `update_progress.py` | `migration-audit <slug>` | Rescan sources and enforce the pre-deletion reconciliation gate | No |
| `update_progress.py` | `migration-finalize <slug>` | Persist `retain`, `delete-approved`, or confirmed `deleted` outcome | Yes, unless `--dry-run` |

Both scripts accept project/tracker location overrides. `--root` takes precedence over
Git-root discovery, while `--dir` takes precedence over
`$PROGRESS_TRACKER_DIR`. Bare plan filenames resolve only through
`$PROGRESS_TRACKER_PLANS_DIR`; otherwise the caller must pass a path.

## 7. Background Jobs & Scheduled Tasks

N/A — the skill has no worker, queue, cron, daemon, or scheduled-task runtime. GitHub
Actions responds to repository pushes and pull requests as part of the delivery pipeline
described in §10, not as application background processing.

## 8. External Service Integrations

Runtime use is local and filesystem-based. The scripts invoke Git only to discover a
project root and use `uv` as the documented Python runner. They do not authenticate to or
call GitHub, GitLab, Redmine, Jira, or another ticket service; ticket values are stored
verbatim.

Distribution instructions name external installers and marketplaces:

| Integration | Role | Configuration/source |
|---|---|---|
| Git | Project-root discovery and version control | `resolve_project_root()` in `new_progress.py` |
| uv | PEP 723 Python provisioning and command execution | Script metadata, README, CI, and scenario runner |
| GitHub Actions | Repository verification on push and pull request | `.github/workflows/ci.yml` |
| Claude Code plugin marketplace | Install the skill and dedicated agent | `.claude-plugin/` manifests |
| Codex plugin marketplace | Install the canonical skill payload | `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` |
| `npx skills` | Cross-agent skill-only installation | README installation instructions |

## 9. Database / Data Stores

N/A — the project owns no relational or embedded database. Persistent state consists of
version-controlled Markdown and JSON files:

- installed project trackers (`INDEX.md`, item `PROGRESS.md` files, plan snapshots, and
  migration records);
- bundled Markdown templates and workflow references;
- plugin and evaluation JSON manifests.

Writes use UTF-8 text files. Migration source identity and approval seals use SHA-256;
entry IDs use a content-derived BLAKE2b digest.

## 10. Environments & Deployment

### Environments

| Environment | Definition |
|---|---|
| Local development | A Git checkout with Bash, `uv`, and the repository files; Python 3.14 is provisioned by `uv` for the main test gate |
| GitHub Actions CI | Ubuntu runner executing Python 3.14 tests, Ruff 0.16.0, and `scripts/verify.sh` |
| Installed consumer project | Any project where an agent runtime loads the skill and the user has write access to a project-local tracker directory |

There are no staging or production application environments because this repository
ships a skill package rather than a hosted service.

### Deployment Pipeline

CI runs on every push and pull request in this order:

1. Install `uv` and Python 3.14.
2. Run the pytest suites under `skills/progress-tracker/scripts/`.
3. Install and run Ruff 0.16.0.
4. Run `bash scripts/verify.sh`, which repeats deterministic tests and verifies
   cross-file contracts and packaging metadata.

Publishing is version-driven rather than performed by a deployment workflow. A
user-visible skill change must update the identical `version` values in the Claude and
Codex plugin manifests; consumers then refresh or reinstall through their selected
marketplace/install route.

### Configuration Hierarchy

| Setting | Resolution order |
|---|---|
| Project root | `--root` → `git rev-parse --show-toplevel` → current working directory |
| Tracker directory | `--dir` → `$PROGRESS_TRACKER_DIR` → `progress` |
| Bare plan filename | `$PROGRESS_TRACKER_PLANS_DIR` only; otherwise pass an explicit path |
| Python version | PEP 723 `requires-python >=3.14`, mirrored by CI and `verify.sh` checks |
| Ruff version | Exact version pinned in `.github/workflows/ci.yml` |
| Plugin version | Equal values in `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` |
