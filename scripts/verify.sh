#!/usr/bin/env bash
# Consistency gate for the progress-tracker skill repo. Requires Bash + Python 3.
# Every check prints PASS/FAIL; any failure exits 1.
set -u
cd "$(dirname "$0")/.."

SKILL_DIR="skills/progress-tracker"
SKILL_MD="$SKILL_DIR/SKILL.md"
REFS="$SKILL_DIR/references"
SCRIPTS="$SKILL_DIR/scripts"

fail=0
report() { # $1=status(0 ok) $2=label $3=detail-on-fail
  if [ "$1" -eq 0 ]; then
    echo "PASS  $2"
  else
    echo "FAIL  $2${3:+ — $3}"
    fail=1
  fi
}

# 1. Placeholder consistency: every {{X}} the script substitutes must exist
#    in the template, and vice versa.
script_placeholders=$(grep -oE '\{\{[A-Z_]+\}\}' "$SCRIPTS/new_progress.py" | sort -u)
template_placeholders=$(grep -oE '\{\{[A-Z_]+\}\}' "$REFS/PROGRESS.template.md" | sort -u)
placeholder_diff=$(diff <(echo "$script_placeholders") <(echo "$template_placeholders"))
report "$([ -z "$placeholder_diff" ]; echo $?)" "script/template placeholders match exactly" "$placeholder_diff"

# 2. TABLE_HEADER_MARKER in the script must equal INDEX.template.md's header row.
marker=$(grep 'TABLE_HEADER_MARKER = ' "$SCRIPTS/new_progress.py" | sed -E 's/.*TABLE_HEADER_MARKER = "(.*)"/\1/')
index_header=$(grep '^| Status |' "$REFS/INDEX.template.md" | head -1)
report "$([ "$marker" = "$index_header" ]; echo $?)" "TABLE_HEADER_MARKER matches INDEX.template.md header" "script:[$marker] template:[$index_header]"

# 3. Status enum and transition diagram identical across SKILL.md,
#    workflow.md, and INDEX.template.md.
lifecycle_ok=1
python3 - <<'PY' && lifecycle_ok=0
from pathlib import Path

paths = [
    Path("skills/progress-tracker/SKILL.md"),
    Path("skills/progress-tracker/references/workflow.md"),
    Path("skills/progress-tracker/references/INDEX.template.md"),
]
start = "<!-- STATUS_LIFECYCLE_START -->"
end = "<!-- STATUS_LIFECYCLE_END -->"
expected_enum = (
    "Status enum: `planning`, `in-progress`, `review`, `blocked`, `done`, `abandoned`"
)
expected_diagram = """```
planning → in-progress → review → done
                       ↘ abandoned
         ↘ blocked → in-progress
```"""

blocks = []
for path in paths:
    text = path.read_text(encoding="utf-8")
    assert text.count(start) == 1 and text.count(end) == 1, f"lifecycle markers in {path}"
    block = text[text.index(start) : text.index(end) + len(end)]
    assert expected_enum in block, f"fixed status enum in {path}"
    assert expected_diagram in block, f"transition diagram in {path}"
    blocks.append(block)
assert all(block == blocks[0] for block in blocks[1:]), "lifecycle blocks differ"
PY
report "$lifecycle_ok" "status enum and transition diagram match exactly" "lifecycle block validation failed"

# 4. Reference integrity. SKILL.md paths are relative to the skill root;
#    README.md/AGENTS.md paths are repo-relative.
dead_refs=""
for p in $(grep -hoE '(references|scripts|agents)/[A-Za-z0-9_.-]+\.(md|sh|py|yaml)' "$SKILL_MD" | sort -u); do
  [ -f "$SKILL_DIR/$p" ] || dead_refs="$dead_refs SKILL.md:$p"
done
for p in $(grep -hoE 'skills/progress-tracker/[A-Za-z0-9/_.-]+\.(md|sh|py|yaml)' README.md AGENTS.md 2>/dev/null | sort -u); do
  [ -f "$p" ] || dead_refs="$dead_refs $p"
done
for p in $(grep -hoE '\]\((docs/[a-z-]+\.md|AGENTS\.md|evals/README\.md)\)' README.md AGENTS.md 2>/dev/null | sed -E 's/.*\((.*)\)/\1/' | sort -u); do
  [ -f "$p" ] || dead_refs="$dead_refs $p"
done
report "$([ -z "$dead_refs" ]; echo $?)" "cited reference/doc paths exist" "missing:$dead_refs"

# 5. Relative links in files copied into a project must resolve within the
#    scaffolded tracker; skill-installation paths are not present there.
scaffold_links_ok=1
python3 - <<'PY' && scaffold_links_ok=0
import posixpath
import re
from pathlib import Path, PurePosixPath

sources = {
    Path("skills/progress-tracker/references/tracker-readme.md"): PurePosixPath("README.md"),
    Path("skills/progress-tracker/references/INDEX.template.md"): PurePosixPath("INDEX.md"),
    Path("skills/progress-tracker/references/PROGRESS.template.md"): PurePosixPath("_template/PROGRESS.md"),
    Path("skills/progress-tracker/references/plans-readme.md"): PurePosixPath("_plans/README.md"),
}
available = {str(path) for path in sources.values()}
link_re = re.compile(r"\]\(([^)]+)\)")
for source, virtual_path in sources.items():
    for link in link_re.findall(source.read_text(encoding="utf-8")):
        if "://" in link or link.startswith(("#", "mailto:")) or "{{" in link:
            continue
        target = posixpath.normpath(str(virtual_path.parent / link.split("#", 1)[0]))
        assert target in available, f"{source}: unresolved scaffold link {link!r} -> {target!r}"
PY
report "$scaffold_links_ok" "scaffolded relative markdown links resolve" "scaffold link validation failed"

# 6. Skill-facing command examples must resolve the bundled script through
#    the installed skill directory, never through the target project's cwd.
portable_command_ok=0
grep -q 'uv run <skill-dir>/scripts/new_progress.py' "$SKILL_MD" || portable_command_ok=1
grep -q 'uv run <skill-dir>/scripts/new_progress.py' "$REFS/tracker-readme.md" || portable_command_ok=1
grep -qE 'uv run (scripts/new_progress.py|new_progress.py)' "$SKILL_MD" "$REFS/tracker-readme.md" \
  && portable_command_ok=1
report "$portable_command_ok" "scaffold command uses the installed skill path" "found a cwd-relative command"

# 7. Plugin manifests: parseable, names consistent with the skill layout.
plugin_ok=1
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY' && plugin_ok=0
import json
p = json.load(open(".claude-plugin/plugin.json"))
m = json.load(open(".claude-plugin/marketplace.json"))
assert p["name"] == "progress-tracker", "plugin.json name"
assert any(e["name"] == "progress-tracker" for e in m["plugins"]), "marketplace entry"
parts = p["version"].split(".")
assert len(parts) == 3 and all(part.isdigit() for part in parts), "plugin.json semver"
PY
else
  plugin_ok=0  # python3 unavailable — skip rather than fail
fi
report "$plugin_ok" "plugin manifests parse and name progress-tracker" ""

# 8. Codex agents/openai.yaml metadata is complete.
openai_yaml_ok=1
python3 - <<'PY' && openai_yaml_ok=0
from pathlib import Path

lines = Path("skills/progress-tracker/agents/openai.yaml").read_text().splitlines()
assert lines[0] == "interface:"
values = {}
for line in lines[1:]:
    key, value = line.strip().split(": ", 1)
    assert value.startswith('"') and value.endswith('"')
    values[key] = value[1:-1]
assert set(values) == {"display_name", "short_description", "default_prompt"}
assert values["display_name"] == "Progress Tracker"
assert 10 <= len(values["short_description"]) <= 64
assert "$progress-tracker" in values["default_prompt"]
PY
report "$openai_yaml_ok" "Codex agents/openai.yaml metadata is complete" "openai.yaml validation failed"

# 9. CLAUDE.md symlink sanity.
link=$(readlink CLAUDE.md 2>/dev/null || true)
report "$([ "$link" = "AGENTS.md" ]; echo $?)" "CLAUDE.md is a symlink to AGENTS.md" "got: ${link:-not a symlink}"

# 10. Dedicated agent definition preloads the skill.
agent_skill_ref=$(grep -A2 '^skills:' agents/progress-tracker.md 2>/dev/null | grep -c 'progress-tracker')
report "$([ "$agent_skill_ref" -ge 1 ]; echo $?)" "agents/progress-tracker.md preloads the progress-tracker skill" ""

# 11. SKILL.md frontmatter sanity: description word count in a reasonable range.
description_words=$(awk 'NR >= 4 { if ($0 == "---") exit; print }' "$SKILL_MD" | wc -w | tr -d ' ')
report "$([ "$description_words" -ge 40 ] && [ "$description_words" -le 160 ]; echo $?)" \
  "SKILL.md trigger description stays concise" "$description_words words (expected 40..160)"

# 12. No leftover Kdan-specific coupling residue in the parts of the skill
#     that get scaffolded/copied into a user's project (references/, the
#     script). SKILL.md/README.md/AGENTS.md/docs/design-decisions.md are
#     excluded — they legitimately *discuss* these terms as history/rationale
#     or as the one intentional cross-reference to the Kdan-internal sibling.
kdan_residue=$(grep -rniE 'redmine|gitlab|kdan|ticket-sync|~/\.claude/plans|~/Documents/projects|WORKSPACE_ROOT' \
  "$REFS"/*.md "$SCRIPTS"/new_progress.py 2>/dev/null)
report "$([ -z "$kdan_residue" ]; echo $?)" "no leftover Kdan-specific coupling residue in references/scripts" "$kdan_residue"

# 13. Trigger matrix shape (if present).
if [ -f evals/trigger-matrix.json ]; then
  trigger_matrix_ok=1
  python3 - <<'PY' && trigger_matrix_ok=0
import json

cases = json.load(open("evals/trigger-matrix.json"))
assert len(cases) >= 8
assert all(set(case) == {"id", "prompt", "expected", "reason"} for case in cases)
assert len({case["id"] for case in cases}) == len(cases)
assert all(case["prompt"].strip() and case["reason"].strip() for case in cases)
assert set(case["expected"] for case in cases) <= {"progress-tracker", "not-progress-tracker"}
PY
  report "$trigger_matrix_ok" "trigger matrix has valid shape" "trigger-matrix.json validation failed"
fi

# 14. Unit + integration test suite passes.
pytest_ok=1
if command -v uv >/dev/null 2>&1; then
  (cd "$SCRIPTS" && uv run --with pytest python3 -m pytest . -q) >/tmp/progress-tracker-pytest.log 2>&1 && pytest_ok=0
elif python3 -c "import pytest" >/dev/null 2>&1; then
  (cd "$SCRIPTS" && python3 -m pytest . -q) >/tmp/progress-tracker-pytest.log 2>&1 && pytest_ok=0
else
  echo "SKIP  scaffold-script test suite (no uv or pytest available)"
  pytest_ok=0
fi
report "$pytest_ok" "scaffold-script test suite passes" "see /tmp/progress-tracker-pytest.log"

# 15. Eval scenario grader regression tests pass (if present).
if [ -f evals/scripts/test_grade_scenarios.py ]; then
  scenario_tests_ok=1
  python3 evals/scripts/test_grade_scenarios.py >/tmp/progress-tracker-scenario-tests.log 2>&1 && scenario_tests_ok=0
  report "$scenario_tests_ok" "scenario grader regression tests pass" "see /tmp/progress-tracker-scenario-tests.log"
fi

# 16. Shell script syntax.
shell_syntax_ok=0
shell_scripts=$(find evals/scripts -name '*.sh' 2>/dev/null)
if [ -n "$shell_scripts" ]; then
  bash -n $shell_scripts || shell_syntax_ok=1
fi
report "$shell_syntax_ok" "eval shell script syntax is valid" "bash -n failed"

echo
if [ "$fail" -eq 0 ]; then echo "verify.sh: all checks passed"; else echo "verify.sh: FAILURES above"; fi
exit "$fail"
