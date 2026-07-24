# Evaluation suite

Two complementary layers protect progress-tracker, both **script-first** — no
model/LLM call is required to run either, unlike doc-architect's model-graded
stack-detection suite (see [`docs/design-decisions.md`](../docs/design-decisions.md)
for why that difference is deliberate: this skill's core, `new_progress.py`,
is a deterministic script, not a model judgment call).

1. **Lifecycle scenarios** run the real scaffold script end-to-end in a
   disposable git repository and grade filesystem/content invariants —
   creation, multi-scope expansion, plan-snapshot linking, idempotent
   refusal, close-out edits, and custom `--dir`/`--root` overrides.
2. **Trigger matrix** records the intended boundary for when an agent should
   (or should not) reach for this skill, including the boundary against
   doc-architect's differently-scoped `PROGRESS.md` harness module.

The primary correctness gate is actually neither of these — it's
[`skills/progress-tracker/scripts/test_new_progress.py`](../skills/progress-tracker/scripts/test_new_progress.py)
(pytest), which unit- and integration-tests `new_progress.py` directly. The
scenarios here exist to additionally prove the **documented lifecycle** (the
sequence of script + manual edits SKILL.md describes) holds end-to-end, and
to protect the grading logic itself from false-greening.

## Layout

```
evals/
├── README.md                  # this file
├── scenarios/                 # 6 disposable-repo lifecycle scenarios
│   └── */scenario.json        # steps (run/write/edit) + deterministic checks
├── trigger-matrix.json        # 7 positive + 4 negative/boundary prompts
└── scripts/
    ├── run_scenarios.py       # runs each scenario's steps against a disposable git repo
    ├── run_scenarios.sh       # thin bash entry point → run_scenarios.py
    ├── grade_scenarios.py     # deterministic grader (filesystem/content checks)
    └── test_grade_scenarios.py # free false-green regression tests for the grader
```

## Scenario contract

Each `scenario.json` has `description`, `steps`, and `checks`.

**Steps** (executed in order, against a fresh `git init`-ed temp directory):

| Step type | Fields | Effect |
|---|---|---|
| `run` | `args` | Invokes `new_progress.py` with these CLI args |
| `run_expect_fail` | `args`, `expect_stderr_contains` (optional) | Invokes it and asserts a non-zero exit (and optionally a stderr substring) |
| `write` | `path`, `content` | Writes a file directly (e.g. a plan file to later pass via `--plan`) |
| `edit` | `glob`, `find`, `replace` | Simulates a manual/agent edit (e.g. the "after completing work" Outcome fill-in), applied to every file matching `glob` |

**Checks** (evaluated against the final repo state):

| Check type | Shape | Meaning |
|---|---|---|
| `files_exist` | list of glob patterns | Each pattern must match ≥1 path |
| `files_absent` | list of glob patterns | Each pattern must match 0 paths |
| `content_contains` | list of `{glob, text}` | The matched file(s) must contain `text` |
| `content_not_contains` | list of `{glob, text}` | The matched file(s) must not contain `text` |
| `content_count` | list of `{glob, text, count}` | `text` must appear exactly `count` times in the matched file(s) |

## Running

```bash
# all scenarios
python3 evals/scripts/run_scenarios.py
# or: ./evals/scripts/run_scenarios.sh

# one scenario, by directory name
python3 evals/scripts/run_scenarios.py create-with-plan

# free grader regression tests (no live script run)
python3 evals/scripts/test_grade_scenarios.py
```

Both are free and fast (no API key, no network) — they run on every
`verify.sh` invocation and every CI push/PR.

## Adding a scenario

1. Create `evals/scenarios/<name>/scenario.json` with `description`, `steps`,
   `checks`.
2. Run `python3 evals/scripts/run_scenarios.py <name>` to confirm it passes
   against the real script.
3. If the scenario exercises a new check pattern, add a regression test to
   `test_grade_scenarios.py` in the same change — an unprotected check is a
   check that can silently stop meaning anything.

## Trigger boundary matrix

`trigger-matrix.json` lists representative prompts with expected outcomes
`progress-tracker` or `not-progress-tracker`, including the boundary against
doc-architect's `PROGRESS.md` harness module (a single repo-root
agent-resume file — a different concept from this skill's multi-item dated
journal under `progress/`). `scripts/verify.sh` checks its shape and that
every case has a non-empty prompt and reason. It is a review contract, not a
live-eval — proving metadata-only trigger selection would require running
the surrounding skill catalog, which is out of scope here.

## Known limits

- Scenario grading covers deterministic filesystem/content invariants, not
  writing quality — there's no prose to grade, since this skill's outputs are
  templated, not generated prose.
- The trigger matrix is a documented contract for human/agent review, not a
  live classifier test.
