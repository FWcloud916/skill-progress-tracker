# progress-tracker

An agent skill that tracks local development progress for tasks spanning a
full lifecycle (investigate → fix → test → PR/MR) — across a single scope or
several — for any project.

## What it does

- **Scaffold** — creates a dated, kebab-case-slugged item folder under a
  `progress/` directory (configurable) with a filled-in `PROGRESS.md`, and
  appends a row to `INDEX.md`. First use in a project auto-scaffolds the
  tracker directory's supporting files.
- **Migration guard, script-gated** — before first use, inventories existing
  tracking documents and their pointers and asks whether to migrate.
  `migration-inventory` scans a legacy source **whole-document** (never just
  an "in progress" section), can scaffold an empty tracker before destination
  creation, and `migration-audit` is the pre-deletion gate: it
  fails while any actionable/ambiguous entry lacks a valid `migrated` or
  `excluded` disposition and destination, migrated Evidence is absent or
  non-unique, any generated record field changed,
  any old path/name or changed link is unverified, or the pre-deletion human
  sign-off checklist is incomplete. `migration-finalize` durably records the
  user's retain/delete decision without deleting source files.
- **Multi-scope, tool-agnostic** — `--scope name[:branch[:ticket]]` accepts
  any free-form label (a service, a package, a sibling repo — not validated
  against a directory) and any ticket format (serial, `#123`, `JIRA-111`, a
  URL — kept verbatim, no normalization). Literal delimiters use backslash
  escaping.
- **Plan integration, optional** — `--plan <path>` copies whatever planning
  artifact you have (Claude Code plan-mode output, a draft doc, anything)
  into a slug-namespaced, version-controlled snapshot linked from the item.
- **Lifecycle automation** — `update_progress.py` validates transitions,
  updates item and INDEX statuses together, closes outcomes, and audits drift,
  duplicates, missing rows, and stale rows.
- **Canonical status lifecycle** — `planning → in-progress ⇄ review → done`,
  with blocked/resume and explicit abandonment paths, defined in `SKILL.md`
  and mirrored everywhere else.
- **Human-only cleanup** — the script and any agent using this skill never
  delete item folders or INDEX rows; that stays a manual decision.

## Install

### Option 1 — Codex plugin (recommended for Codex)

The repo is a Codex plugin marketplace. Add it once, then install the plugin:

```bash
codex plugin marketplace add FWcloud916/skill-progress-tracker
codex plugin add progress-tracker@progress-tracker
```

Start a new Codex conversation after installation so the bundled skill is
loaded. Future published updates can be picked up by refreshing the Git
marketplace and reinstalling the plugin.

### Option 2 — Claude Code plugin (recommended for Claude Code)

The repo is a Claude Code plugin marketplace; installing the plugin gives you
the skill **and** the dedicated `progress-tracker` agent in one step, with
version-pinned updates:

```
/plugin marketplace add FWcloud916/skill-progress-tracker
/plugin install progress-tracker@progress-tracker
```

### Option 3 — skills CLI (any of 70+ agents)

[vercel-labs/skills](https://github.com/vercel-labs/skills) installs the skill
for the agent(s) you pick (Claude Code, Cursor, Codex, and more), creating any
missing directories along the way:

```bash
npx skills add FWcloud916/skill-progress-tracker                      # interactive: pick agents + scope
npx skills add FWcloud916/skill-progress-tracker -g -a claude-code -y # non-interactive, global
```

This route installs the skill only. To also use the dedicated Claude Code
agent, add the agent symlink from Option 4's last step.

### Option 4 — manual clone + symlink

Pick the layout your runtime reads — `~/.claude/skills` for Claude Code, or
the universal `~/.agents/skills` for runtimes that share it. `mkdir -p` covers
the case where the target directory doesn't exist yet:

```bash
git clone https://github.com/FWcloud916/skill-progress-tracker.git

# Claude Code layout
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skill-progress-tracker/skills/progress-tracker" ~/.claude/skills/progress-tracker

# or: universal agents layout
mkdir -p ~/.agents/skills
ln -s "$(pwd)/skill-progress-tracker/skills/progress-tracker" ~/.agents/skills/progress-tracker

# optional: dedicated Claude Code agent (requires the skill symlink above)
mkdir -p ~/.claude/agents
ln -s "$(pwd)/skill-progress-tracker/agents/progress-tracker.md" ~/.claude/agents/progress-tracker.md
```

The agent definition preloads the skill via its `skills:` frontmatter, so the
skill symlink is a prerequisite for the agent symlink. The Codex plugin and
standalone-skill routes do not install this Claude Code-specific agent.

## Use

**As a skill** — invoke `$progress-tracker` in Codex, `/progress-tracker` in
Claude Code, or just ask in natural language:

- "start tracking this refactor" / "I need a progress note for this task" → create
- "update the progress item for X" → update
- "check the tracker for status drift" → audit
- "close out the subscription-refund progress item" → close-out

**As a dedicated agent** (requires the agent symlink):

- In any session, Claude Code can delegate item creation/update/close-out to
  the `progress-tracker` subagent, which runs the scaffold script and reports
  back what it wrote.

**Directly**, without an agent:

```bash
uv run skills/progress-tracker/scripts/new_progress.py subscription-refund \
  --scope "api:feature/refund:JIRA-111,worker:feature/refund" \
  --ticket EPIC-100 \
  --plan ./my-plan.md \
  --title "Refund flow rework"

uv run skills/progress-tracker/scripts/update_progress.py update subscription-refund \
  --status in-progress --work-log "Implemented validation."

uv run skills/progress-tracker/scripts/update_progress.py close subscription-refund \
  --outcome "Merged and deployed." --pr "PR #42"

uv run skills/progress-tracker/scripts/update_progress.py check
```

## In a Kdan Mobile workspace?

Kdan Mobile's internal `kdan-workflow` repo ships a workspace-specific
sibling skill, `progress-note`, wired into that workspace's ticket system and
multi-service layout. Use that one there; use `progress-tracker` everywhere
else.

## Develop

Working on the skill itself? Read [AGENTS.md](AGENTS.md) first, then verify
any change:

```bash
bash scripts/verify.sh                                                          # consistency gate
uv run --with pytest python3 -m pytest skills/progress-tracker/scripts/ -v      # unit + integration tests
python3 evals/scripts/test_grade_scenarios.py                                    # free scenario grader tests
python3 evals/scripts/run_scenarios.py                                           # end-to-end lifecycle scenarios
```

## Project structure

```
progress-tracker/
├── .agents/plugins/  # marketplace.json — Codex marketplace catalog
├── .claude-plugin/   # plugin.json + marketplace.json — Claude Code packaging
├── .codex-plugin/    # plugin.json — Codex plugin packaging
├── skills/
│   └── progress-tracker/
│       ├── SKILL.md      # canonical entry point: lifecycle, args, status enum
│       ├── agents/       # Codex UI metadata (openai.yaml)
│       ├── references/   # workflow spec + item/index templates + seed READMEs
│       └── scripts/      # create/update/check CLIs + their pytest suites
├── agents/           # dedicated agent definition (preloads the skill)
├── AGENTS.md         # maintainer guide for this repo (CLAUDE.md is a symlink to it)
├── docs/             # design-decisions.md — why the skill is built this way
├── scripts/          # verify.sh — consistency gate for changes to this repo
└── evals/            # lifecycle scenarios + trigger matrix
```

## Documentation

| Doc | What it covers |
|---|---|
| [SKILL.md](skills/progress-tracker/SKILL.md) | Lifecycle stages, scaffold-script arguments, status enum |
| [AGENTS.md](AGENTS.md) | Maintainer guide: hard constraints, the verify gate |
| [docs/design-decisions.md](docs/design-decisions.md) | Decision log with rationale: generic scope model, script-first eval strategy |
| [workflow.md](skills/progress-tracker/references/workflow.md) | Full workflow spec: folder structure, field semantics, cleanup policy |
| [PROGRESS.template.md](skills/progress-tracker/references/PROGRESS.template.md) | The item template |
| [INDEX.template.md](skills/progress-tracker/references/INDEX.template.md) | The item-list seed |
| [evals/README.md](evals/README.md) | Scenario + trigger-matrix strategy and how to run them |
