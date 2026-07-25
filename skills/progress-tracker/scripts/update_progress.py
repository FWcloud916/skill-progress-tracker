#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Update, close, or audit progress-tracker items safely.

Usage:
    uv run <skill-dir>/scripts/update_progress.py update <slug> [options]
    uv run <skill-dir>/scripts/update_progress.py close <slug> --outcome TEXT [options]
    uv run <skill-dir>/scripts/update_progress.py check [options]
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
from datetime import date
from pathlib import Path

from new_progress import (
    DEFAULT_TRACKER_DIRNAME,
    parse_scope,
    render_scope_rows,
    require_project_descendant,
    resolve_project_root,
    resolve_tracker_dir,
    validate_single_line,
)

STATUS_VALUES = ("planning", "in-progress", "review", "blocked", "done", "abandoned")
ACTIVE_STATUS_VALUES = ("planning", "in-progress", "review", "blocked")
FINAL_STATUS_VALUES = ("done", "abandoned")
ALLOWED_TRANSITIONS = {
    "planning": {"in-progress", "abandoned"},
    "in-progress": {"review", "blocked", "abandoned"},
    "review": {"in-progress", "done", "abandoned"},
    "blocked": {"in-progress", "abandoned"},
    "done": set(),
    "abandoned": set(),
}

STATUS_LINE_RE = re.compile(r"^\*\*Status:\*\* ([^\n]+)$", re.MULTILINE)
SLUG_LINE_RE = re.compile(r"^\*\*Slug:\*\* ([^\n]+)$", re.MULTILINE)
INDEX_STATUS_RE = re.compile(r"^(\|\s*)`([^`]+)`(\s*\|)")
SCOPE_TABLE_HEADER = "| Scope | Branch | Ticket | Notes |\n|---|---|---|---|\n"


def _location_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dir",
        default=None,
        metavar="DIRNAME",
        help=(
            "Tracker directory relative to the project root. Defaults to "
            "$PROGRESS_TRACKER_DIR, then 'progress'."
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        metavar="PATH",
        help="Project root. Defaults to git top level, then the current directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update, close, or audit local development progress items."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    update = commands.add_parser("update", help="Update a living progress item.")
    update.add_argument("slug", help="Existing item's stable slug.")
    update.add_argument("--status", choices=ACTIVE_STATUS_VALUES)
    update.add_argument(
        "--scope",
        help=(
            "Replacement scope table using the same escaped "
            "name[:branch[:ticket]],... syntax as new_progress.py."
        ),
    )
    update.add_argument("--work-log", help="Single-line note appended under today's Work log.")
    update.add_argument(
        "--complete-task",
        action="append",
        default=[],
        metavar="TEXT",
        help="Check an exact Task list entry; repeat for multiple entries.",
    )
    _location_args(update)

    close = commands.add_parser("close", help="Close an item as done or abandoned.")
    close.add_argument("slug", help="Existing item's stable slug.")
    close.add_argument("--status", choices=FINAL_STATUS_VALUES, default="done")
    close.add_argument("--outcome", required=True, help="Concise final outcome summary.")
    close.add_argument("--pr", default="N/A", help="PR/MR or commit reference.")
    close.add_argument("--follow-up", default="None", help="Follow-up work, or 'None'.")
    close.add_argument("--work-log", help="Optional final single-line Work log note.")
    _location_args(close)

    check = commands.add_parser("check", help="Audit tracker/index consistency without writes.")
    _location_args(check)
    return parser


def resolve_location(root_arg: str | None, dirname_arg: str | None) -> tuple[Path, Path, str]:
    project_root = resolve_project_root(root_arg)
    dirname = dirname_arg or os.environ.get("PROGRESS_TRACKER_DIR") or DEFAULT_TRACKER_DIRNAME
    validate_single_line(dirname, "--dir")
    tracker_dir, normalized = resolve_tracker_dir(project_root, dirname)
    if not tracker_dir.is_dir():
        sys.exit(f"ERROR: tracker directory not found: {tracker_dir}")
    return project_root, tracker_dir, normalized


def metadata_value(content: str, pattern: re.Pattern[str], label: str, path: Path) -> str:
    matches = pattern.findall(content)
    if len(matches) != 1:
        sys.exit(f"ERROR: expected exactly one {label} field in {path}; found {len(matches)}")
    return matches[0].strip()


def find_item(tracker_dir: Path, slug: str, project_root: Path) -> tuple[Path, str]:
    matches: list[tuple[Path, str]] = []
    for progress_path in sorted(tracker_dir.glob("*/PROGRESS.md")):
        if progress_path.parent.name.startswith("_"):
            continue
        require_project_descendant(progress_path, project_root, "progress item")
        content = progress_path.read_text(encoding="utf-8")
        match = SLUG_LINE_RE.search(content)
        if match and match.group(1).strip() == slug:
            matches.append((progress_path, content))
    if not matches:
        sys.exit(f"ERROR: no progress item found for slug {slug!r} in {tracker_dir}")
    if len(matches) > 1:
        paths = "\n".join(f"  {path}" for path, _ in matches)
        sys.exit(f"ERROR: multiple progress items found for slug {slug!r}:\n{paths}")
    return matches[0]


def index_data_rows(index_content: str, index_path: Path) -> list[tuple[int, str]]:
    lines = index_content.splitlines(keepends=True)
    try:
        header_idx = next(i for i, line in enumerate(lines) if line.startswith("| Status | Item |"))
    except StopIteration:
        sys.exit(f"ERROR: item table header not found in {index_path}")
    if header_idx + 1 >= len(lines) or not lines[header_idx + 1].startswith("|---"):
        sys.exit(f"ERROR: item table separator not found in {index_path}")
    rows: list[tuple[int, str]] = []
    for idx in range(header_idx + 2, len(lines)):
        if not lines[idx].startswith("|"):
            break
        rows.append((idx, lines[idx]))
    return rows


def find_index_row(
    index_content: str, index_path: Path, item_folder: str
) -> tuple[list[str], int, str]:
    lines = index_content.splitlines(keepends=True)
    folder_marker = f"{item_folder}/"
    matches = [
        (idx, line)
        for idx, line in index_data_rows(index_content, index_path)
        if folder_marker in line
    ]
    if not matches:
        sys.exit(f"ERROR: INDEX row not found for item folder {item_folder!r} in {index_path}")
    if len(matches) > 1:
        sys.exit(f"ERROR: duplicate INDEX rows found for item folder {item_folder!r}")
    idx, line = matches[0]
    return lines, idx, line


def index_status(row: str, index_path: Path) -> str:
    match = INDEX_STATUS_RE.match(row)
    if not match:
        sys.exit(f"ERROR: malformed INDEX status cell in {index_path}: {row.rstrip()!r}")
    return match.group(2)


def replace_metadata(content: str, field: str, value: str, path: Path) -> str:
    pattern = re.compile(rf"^\*\*{re.escape(field)}:\*\* [^\n]*$", re.MULTILINE)
    updated, count = pattern.subn(f"**{field}:** {value}", content, count=1)
    if count != 1:
        sys.exit(f"ERROR: expected exactly one {field} field in {path}; found {count}")
    return updated


def replace_scope_table(content: str, scope_arg: str, path: Path) -> str:
    entries = parse_scope(scope_arg)
    start = content.find(SCOPE_TABLE_HEADER)
    if start == -1:
        sys.exit(f"ERROR: Scope table header not found in {path}")
    body_start = start + len(SCOPE_TABLE_HEADER)
    body_end = content.find("\n\n## Background & goals", body_start)
    if body_end == -1:
        sys.exit(f"ERROR: Scope table end not found in {path}")
    return content[:body_start] + render_scope_rows(entries) + content[body_end:]


def append_work_log(content: str, note: str, today: str, path: Path) -> str:
    validate_single_line(note, "--work-log")
    section_start = content.find("## Work log")
    section_end = content.find("\n## Outcome", section_start)
    if section_start == -1 or section_end == -1:
        sys.exit(f"ERROR: Work log or Outcome section not found in {path}")
    section = content[section_start:section_end].rstrip()
    heading = f"### {today}"
    if heading in section:
        heading_start = section.index(heading)
        next_heading = section.find("\n### ", heading_start + len(heading))
        insert_at = len(section) if next_heading == -1 else next_heading
        before = section[:insert_at].rstrip()
        after = section[insert_at:]
        section = f"{before}\n- {note}{after}"
    else:
        section = f"{section}\n\n{heading}\n\n- {note}"
    return content[:section_start] + section + "\n" + content[section_end:]


def complete_tasks(content: str, tasks: list[str], path: Path) -> str:
    updated = content
    for task in tasks:
        validate_single_line(task, "--complete-task")
        section_start = updated.find("## Task list")
        section_end = updated.find("\n## Work log", section_start)
        if section_start == -1 or section_end == -1:
            sys.exit(f"ERROR: Task list or Work log section not found in {path}")
        section = updated[section_start:section_end]
        entry_re = re.compile(r"^- \[(?P<mark>[ x])\] (?P<body>[^\n]*(?:\n  [^\n]*)*)", re.MULTILINE)
        matches: list[tuple[re.Match[str], str]] = []
        for match in entry_re.finditer(section):
            logical_text = " ".join(line.strip() for line in match.group("body").splitlines())
            if logical_text == task:
                matches.append((match, match.group("mark")))
        if len(matches) > 1:
            sys.exit(f"ERROR: task is ambiguous in {path}: {task!r}")
        if not matches:
            sys.exit(f"ERROR: Task list entry not found in {path}: {task!r}")
        match, mark = matches[0]
        if mark == "x":
            continue
        marker_offset = section_start + match.start() + len("- [")
        updated = updated[:marker_offset] + "x" + updated[marker_offset + 1 :]
    return updated


def replace_outcome(
    content: str, status: str, outcome: str, pr_ref: str, follow_up: str, path: Path
) -> str:
    for label, value in (
        ("--outcome", outcome),
        ("--pr", pr_ref),
        ("--follow-up", follow_up),
    ):
        validate_single_line(value, label)
    outcome_start = content.find("## Outcome")
    if outcome_start == -1:
        sys.exit(f"ERROR: Outcome section not found in {path}")
    rendered = (
        "## Outcome\n\n"
        f"{outcome}\n\n"
        f"**Final status:** {status}\n"
        f"**PR / Commit:** {pr_ref}\n"
        f"**Follow-ups:** {follow_up}\n"
    )
    return content[:outcome_start] + rendered


def validate_transition(current: str, target: str) -> None:
    if current not in STATUS_VALUES:
        sys.exit(f"ERROR: current status is invalid: {current!r}")
    if current == target:
        return
    if target not in ALLOWED_TRANSITIONS[current]:
        allowed = ", ".join(sorted(ALLOWED_TRANSITIONS[current])) or "none"
        sys.exit(
            f"ERROR: invalid status transition {current!r} → {target!r}. "
            f"Allowed from {current!r}: {allowed}"
        )


def update_index_status(lines: list[str], row_idx: int, row: str, target: str) -> str:
    match = INDEX_STATUS_RE.match(row)
    if not match:
        raise AssertionError("index row was validated before status replacement")
    lines[row_idx] = INDEX_STATUS_RE.sub(rf"\g<1>`{target}`\g<3>", row, count=1)
    return "".join(lines)


def print_diff(path: Path, before: str, after: str) -> None:
    if before == after:
        return
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=str(path),
        tofile=str(path),
        lineterm="",
    )
    print("\n".join(diff))


def write_validated_pair(
    progress_path: Path,
    progress_before: str,
    progress_after: str,
    index_path: Path,
    index_before: str,
    index_after: str,
) -> None:
    try:
        if progress_before != progress_after:
            progress_path.write_text(progress_after, encoding="utf-8")
        if index_before != index_after:
            index_path.write_text(index_after, encoding="utf-8")
    except OSError as exc:
        # Best-effort rollback keeps the two status sources aligned on ordinary
        # write failures. Process crashes are outside this guarantee.
        progress_path.write_text(progress_before, encoding="utf-8")
        index_path.write_text(index_before, encoding="utf-8")
        sys.exit(f"ERROR: update failed and was rolled back: {exc}")


def prepare_item(args: argparse.Namespace) -> tuple[Path, str, Path, str, list[str], int, str]:
    project_root, tracker_dir, _ = resolve_location(args.root, args.dir)
    progress_path, progress_content = find_item(tracker_dir, args.slug, project_root)
    index_path = tracker_dir / "INDEX.md"
    require_project_descendant(index_path, project_root, "INDEX.md")
    if not index_path.is_file():
        sys.exit(f"ERROR: INDEX.md not found: {index_path}")
    index_content = index_path.read_text(encoding="utf-8")
    lines, row_idx, row = find_index_row(index_content, index_path, progress_path.parent.name)
    progress_status = metadata_value(progress_content, STATUS_LINE_RE, "Status", progress_path)
    row_status = index_status(row, index_path)
    if progress_status != row_status:
        sys.exit(
            f"ERROR: status drift detected for {args.slug!r}: "
            f"PROGRESS.md={progress_status!r}, INDEX.md={row_status!r}"
        )
    return progress_path, progress_content, index_path, index_content, lines, row_idx, row


def run_mutation(args: argparse.Namespace) -> int:
    if args.command == "update" and not any(
        (args.status, args.scope, args.work_log, args.complete_task)
    ):
        sys.exit(
            "ERROR: update requires at least one of --status, --scope, "
            "--work-log, or --complete-task"
        )

    (
        progress_path,
        progress_before,
        index_path,
        index_before,
        index_lines,
        row_idx,
        row,
    ) = prepare_item(args)
    current_status = metadata_value(progress_before, STATUS_LINE_RE, "Status", progress_path)
    target_status = args.status or current_status
    validate_transition(current_status, target_status)

    today = date.today().isoformat()  # noqa: DTZ011
    progress_after = progress_before
    if target_status != current_status:
        progress_after = replace_metadata(progress_after, "Status", target_status, progress_path)
    if args.command == "update" and args.scope:
        progress_after = replace_scope_table(progress_after, args.scope, progress_path)
    if args.command == "update" and args.complete_task:
        progress_after = complete_tasks(progress_after, args.complete_task, progress_path)
    work_log = args.work_log
    if args.command == "close":
        progress_after = replace_outcome(
            progress_after,
            target_status,
            args.outcome,
            args.pr,
            args.follow_up,
            progress_path,
        )
        work_log = work_log or f"Closed item as `{target_status}`."
    if work_log:
        progress_after = append_work_log(progress_after, work_log, today, progress_path)
    progress_after = replace_metadata(progress_after, "Updated", today, progress_path)

    index_after = index_before
    if target_status != current_status:
        index_after = update_index_status(index_lines, row_idx, row, target_status)

    if args.dry_run:
        print_diff(progress_path, progress_before, progress_after)
        print_diff(index_path, index_before, index_after)
        print("[dry-run] No files written.")
        return 0

    write_validated_pair(
        progress_path,
        progress_before,
        progress_after,
        index_path,
        index_before,
        index_after,
    )
    print(f"Updated: {progress_path}")
    if index_before != index_after:
        print(f"Updated: {index_path}")
    print(f"Status:  {target_status}")
    return 0


def audit_tracker(tracker_dir: Path, project_root: Path) -> list[str]:
    failures: list[str] = []
    index_path = tracker_dir / "INDEX.md"
    require_project_descendant(index_path, project_root, "INDEX.md")
    if not index_path.is_file():
        return [f"INDEX.md not found: {index_path}"]
    index_content = index_path.read_text(encoding="utf-8")
    rows = index_data_rows(index_content, index_path)
    matched_rows: set[int] = set()
    seen_slugs: dict[str, Path] = {}

    for progress_path in sorted(tracker_dir.glob("*/PROGRESS.md")):
        if progress_path.parent.name.startswith("_"):
            continue
        require_project_descendant(progress_path, project_root, "progress item")
        content = progress_path.read_text(encoding="utf-8")
        slug_match = SLUG_LINE_RE.findall(content)
        status_match = STATUS_LINE_RE.findall(content)
        if len(slug_match) != 1:
            failures.append(f"{progress_path}: expected exactly one Slug field")
            continue
        if len(status_match) != 1:
            failures.append(f"{progress_path}: expected exactly one Status field")
            continue
        slug = slug_match[0].strip()
        status = status_match[0].strip()
        if status not in STATUS_VALUES:
            failures.append(f"{progress_path}: invalid status {status!r}")
        if slug in seen_slugs:
            failures.append(f"duplicate slug {slug!r}: {seen_slugs[slug]} and {progress_path}")
        else:
            seen_slugs[slug] = progress_path
        folder_marker = f"{progress_path.parent.name}/"
        row_matches = [(idx, row) for idx, row in rows if folder_marker in row]
        if not row_matches:
            failures.append(f"{progress_path}: missing INDEX row")
            continue
        if len(row_matches) > 1:
            failures.append(f"{progress_path}: duplicate INDEX rows")
            continue
        idx, row = row_matches[0]
        matched_rows.add(idx)
        match = INDEX_STATUS_RE.match(row)
        if not match:
            failures.append(f"{index_path}:{idx + 1}: malformed status cell")
        elif match.group(2) != status:
            failures.append(
                f"{progress_path}: status drift (PROGRESS.md={status!r}, INDEX.md={match.group(2)!r})"
            )

    for idx, row in rows:
        if idx not in matched_rows:
            failures.append(f"{index_path}:{idx + 1}: stale INDEX row: {row.strip()}")
    return failures


def run_check(args: argparse.Namespace) -> int:
    project_root, tracker_dir, _ = resolve_location(args.root, args.dir)
    failures = audit_tracker(tracker_dir, project_root)
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        print(f"check: {len(failures)} problem(s) found")
        return 1
    print(f"PASS  tracker is consistent: {tracker_dir}")
    return 0


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.command == "check":
        return run_check(args)
    return run_mutation(args)


if __name__ == "__main__":
    sys.exit(main())
