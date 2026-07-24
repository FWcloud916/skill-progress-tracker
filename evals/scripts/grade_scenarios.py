#!/usr/bin/env python3
"""Deterministic grader for progress-tracker end-to-end scenarios.

No model/LLM involved: new_progress.py is a deterministic script, so
scenarios are graded purely on filesystem state — no prose matching, no
judge call. See evals/README.md for the overall strategy.

Usage (as a library): grade(repo_dir, checks) -> list[str] of failures.
Usage (as a CLI):      python3 grade_scenarios.py <repo_dir> <scenario.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _matches(repo_dir: Path, pattern: str) -> list[Path]:
    """Resolve a glob pattern (relative to repo_dir) to matching paths.

    Supports both simple names ("progress") and glob wildcards
    ("progress/*-basic-task/PROGRESS.md").
    """
    if any(ch in pattern for ch in "*?["):
        return sorted(repo_dir.glob(pattern))
    candidate = repo_dir / pattern
    return [candidate] if candidate.exists() else []


def check_files_exist(repo_dir: Path, patterns: list[str]) -> list[str]:
    failures = []
    for pattern in patterns:
        if not _matches(repo_dir, pattern):
            failures.append(f"expected a file/dir matching {pattern!r}, found none")
    return failures


def check_files_absent(repo_dir: Path, patterns: list[str]) -> list[str]:
    failures = []
    for pattern in patterns:
        found = _matches(repo_dir, pattern)
        if found:
            failures.append(f"expected no file/dir matching {pattern!r}, found: {found}")
    return failures


def _read_matched(repo_dir: Path, pattern: str) -> str:
    matches = _matches(repo_dir, pattern)
    if not matches:
        raise AssertionError(f"content check: no file matches {pattern!r}")
    # Concatenate all matches' content (usually exactly one match).
    return "\n".join(p.read_text(encoding="utf-8") for p in matches if p.is_file())


def check_content_contains(repo_dir: Path, items: list[dict[str, Any]]) -> list[str]:
    failures = []
    for item in items:
        try:
            content = _read_matched(repo_dir, item["glob"])
        except AssertionError as exc:
            failures.append(str(exc))
            continue
        if item["text"] not in content:
            failures.append(f"{item['glob']!r} does not contain {item['text']!r}")
    return failures


def check_content_not_contains(repo_dir: Path, items: list[dict[str, Any]]) -> list[str]:
    failures = []
    for item in items:
        try:
            content = _read_matched(repo_dir, item["glob"])
        except AssertionError as exc:
            failures.append(str(exc))
            continue
        if item["text"] in content:
            failures.append(f"{item['glob']!r} unexpectedly contains {item['text']!r}")
    return failures


def check_content_count(repo_dir: Path, items: list[dict[str, Any]]) -> list[str]:
    failures = []
    for item in items:
        try:
            content = _read_matched(repo_dir, item["glob"])
        except AssertionError as exc:
            failures.append(str(exc))
            continue
        actual = content.count(item["text"])
        if actual != item["count"]:
            failures.append(
                f"{item['glob']!r}: expected {item['text']!r} to appear {item['count']} time(s), got {actual}"
            )
    return failures


CHECK_HANDLERS = {
    "files_exist": check_files_exist,
    "files_absent": check_files_absent,
    "content_contains": check_content_contains,
    "content_not_contains": check_content_not_contains,
    "content_count": check_content_count,
}


def grade(repo_dir: Path, checks: dict[str, Any]) -> list[str]:
    """Run every check in `checks` against repo_dir, returning all failures."""
    failures: list[str] = []
    for key, handler in CHECK_HANDLERS.items():
        if key in checks:
            failures.extend(handler(repo_dir, checks[key]))
    unknown = set(checks) - set(CHECK_HANDLERS)
    if unknown:
        failures.append(f"unknown check type(s) in scenario.json: {sorted(unknown)}")
    return failures


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: grade_scenarios.py <repo_dir> <scenario.json>", file=sys.stderr)
        return 2
    repo_dir = Path(sys.argv[1])
    scenario = json.loads(Path(sys.argv[2]).read_text())
    failures = grade(repo_dir, scenario.get("checks", {}))
    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        return 1
    print("PASS  all checks satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
