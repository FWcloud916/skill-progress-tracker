#!/usr/bin/env python3
"""Run progress-tracker's end-to-end lifecycle scenarios in disposable repos.

No model/LLM call is involved — the creation and lifecycle scripts are
deterministic, so each scenario runs them directly and grades the resulting
filesystem state. See evals/README.md.

Usage:
    python3 run_scenarios.py                  # all scenarios
    python3 run_scenarios.py create-basic      # one scenario, by directory name
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "evals" / "scenarios"
NEW_PROGRESS_SCRIPT = REPO_ROOT / "skills" / "progress-tracker" / "scripts" / "new_progress.py"
UPDATE_PROGRESS_SCRIPT = (
    REPO_ROOT / "skills" / "progress-tracker" / "scripts" / "update_progress.py"
)
GRADE_SCRIPT = REPO_ROOT / "evals" / "scripts" / "grade_scenarios.py"


def step_script(step: dict) -> Path:
    scripts = {"new": NEW_PROGRESS_SCRIPT, "update": UPDATE_PROGRESS_SCRIPT}
    name = step.get("script", "new")
    if name not in scripts:
        raise RuntimeError(f"unknown script selector: {name!r}")
    return scripts[name]


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def run_step(step: dict, repo_dir: Path) -> None:
    kind = step["type"]
    if kind == "run":
        script = step_script(step)
        result = subprocess.run(
            [sys.executable, str(script), *step["args"]],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"step 'run' {step['args']} failed unexpectedly:\n{result.stderr}"
            )
    elif kind == "run_expect_fail":
        script = step_script(step)
        result = subprocess.run(
            [sys.executable, str(script), *step["args"]],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            raise RuntimeError(f"step 'run_expect_fail' {step['args']} unexpectedly succeeded")
        expect_stderr = step.get("expect_stderr_contains")
        if expect_stderr and expect_stderr not in result.stderr:
            raise RuntimeError(
                f"step 'run_expect_fail' {step['args']}: expected stderr to contain "
                f"{expect_stderr!r}, got:\n{result.stderr}"
            )
    elif kind == "write":
        target = repo_dir / step["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(step["content"], encoding="utf-8")
    elif kind == "edit":
        matches = sorted(repo_dir.glob(step["glob"]))
        if not matches:
            raise RuntimeError(f"step 'edit': no file matches glob {step['glob']!r}")
        for path in matches:
            content = path.read_text(encoding="utf-8")
            if step["find"] not in content:
                raise RuntimeError(
                    f"step 'edit': {path} does not contain {step['find']!r}"
                )
            path.write_text(content.replace(step["find"], step["replace"]), encoding="utf-8")
    else:
        raise RuntimeError(f"unknown step type: {kind!r}")


def run_scenario(name: str) -> tuple[bool, str]:
    scenario_dir = SCENARIOS_DIR / name
    scenario = json.loads((scenario_dir / "scenario.json").read_text())

    with tempfile.TemporaryDirectory(prefix=f"progress-tracker-scenario-{name}-") as tmp:
        # Keep the repository one level below the unique temp root so scenarios
        # can safely assert that `../...` escape targets remain absent.
        repo_dir = Path(tmp) / "repo"
        repo_dir.mkdir()
        init_git_repo(repo_dir)
        try:
            for step in scenario["steps"]:
                run_step(step, repo_dir)
        except RuntimeError as exc:
            return False, f"step failed: {exc}"

        grade_result = subprocess.run(
            [sys.executable, str(GRADE_SCRIPT), str(repo_dir), str(scenario_dir / "scenario.json")],
            capture_output=True,
            text=True,
            check=False,
        )
        if grade_result.returncode != 0:
            return False, grade_result.stdout.strip() or grade_result.stderr.strip()
        return True, "all checks satisfied"


def main() -> int:
    requested = sys.argv[1:]
    all_names = sorted(p.name for p in SCENARIOS_DIR.iterdir() if (p / "scenario.json").exists())
    names = requested or all_names
    unknown = set(names) - set(all_names)
    if unknown:
        print(f"Unknown scenario(s): {sorted(unknown)}", file=sys.stderr)
        print(f"Available: {all_names}", file=sys.stderr)
        return 2

    failed = []
    for name in names:
        ok, detail = run_scenario(name)
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name}  — {detail}")
        if not ok:
            failed.append(name)

    print()
    if failed:
        print(f"run_scenarios.py: {len(failed)}/{len(names)} scenario(s) FAILED: {failed}")
        return 1
    print(f"run_scenarios.py: all {len(names)} scenario(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
