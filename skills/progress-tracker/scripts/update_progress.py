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
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from new_progress import (
    DEFAULT_TRACKER_DIRNAME,
    REFERENCES_DIR,
    markdown_code,
    markdown_table_text,
    parse_scope,
    render_scope_rows,
    require_project_descendant,
    resolve_project_root,
    resolve_tracker_dir,
    validate_single_line,
    validate_slug,
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
CREATED_LINE_RE = re.compile(r"^\*\*Created:\*\* ([^\n]+)$", re.MULTILINE)
INDEX_STATUS_RE = re.compile(r"^(\|\s*)`([^`]+)`(\s*\|)")
SCOPE_TABLE_HEADER = "| Scope | Branch | Ticket | Notes |\n|---|---|---|---|\n"

# ---------------------------------------------------------------------------
# Migration inventory / audit constants
#
# See KNOWN-ISSUE.md KI-001: a prose-only migration audit let an agent treat
# an empty "## Now" section as proof that a legacy source held no actionable
# content, while a "## Next steps" section and a backlog it never inspected
# still held unmigrated work. These constants back a script-enforced,
# whole-document scan that defaults to blocking on anything it does not
# recognize, rather than defaulting to "nothing to see here".
# ---------------------------------------------------------------------------

MIGRATIONS_DIRNAME = "_migrations"

MIGRATION_SOURCES_START = "<!-- MIGRATION_SOURCES_START -->"
MIGRATION_SOURCES_END = "<!-- MIGRATION_SOURCES_END -->"
MIGRATION_DISPOSITIONS_START = "<!-- MIGRATION_DISPOSITIONS_START -->"
MIGRATION_DISPOSITIONS_END = "<!-- MIGRATION_DISPOSITIONS_END -->"
MIGRATION_TABLE_START = "<!-- MIGRATION_TABLE_START -->"
MIGRATION_TABLE_END = "<!-- MIGRATION_TABLE_END -->"
MIGRATION_SIGNOFF_START = "<!-- MIGRATION_SIGNOFF_START -->"
MIGRATION_SIGNOFF_END = "<!-- MIGRATION_SIGNOFF_END -->"

MIGRATION_TABLE_HEADER = "| ID | Kind | Source | Loc | Section | Entry | Disposition | Destination |"
MIGRATION_TABLE_SEPARATOR = "|---|---|---|---|---|---|---|---|"

# A row's Kind is generated, never hand-set; these are the only values
# scan_source() ever produces.
ENTRY_KINDS = ("actionable", "ambiguous", "done", "empty", "historical")
# actionable and ambiguous both block the audit until dispositioned — treating
# "unrecognized" as safe-by-default is the direct fix for KI-001: a heading
# nobody thought to classify no longer gets treated as harmless.
BLOCKING_KINDS = ("actionable", "ambiguous")

# A row's Disposition is hand-filled by whoever resolves the migration.
DISPOSITION_VALUES = ("migrated", "excluded", "archived", "not-applicable")
TBD_CELL = "TBD"
EMPTY_DESTINATION_VALUES = {"", "TBD", "—", "-"}

# Headings that mean "there is unresolved work described under here" —
# generous by design; a false positive here just adds a row to disposition,
# while a missing keyword here is exactly how KI-001 happened.
ACTIONABLE_HEADINGS = (
    "now",
    "current",
    "currently",
    "active",
    "in progress",
    "in-progress",
    "wip",
    "work in progress",
    "next",
    "next steps",
    "next step",
    "next actions",
    "upcoming",
    "todo",
    "to do",
    "to-do",
    "task",
    "tasks",
    "task list",
    "backlog",
    "planned",
    "plan",
    "planning",
    "not started",
    "pending",
    "blocked",
    "blocker",
    "blockers",
    "follow up",
    "follow-up",
    "follow ups",
    "followups",
    "roadmap",
    "remaining",
    "outstanding",
    "action items",
)
# Deliberately conservative: every entry here is a suppression vector, and a
# heading that should have blocked but didn't is exactly KI-001. Anything not
# recognized as historical or actionable falls through to "ambiguous", which
# blocks — so an incomplete list here is safe, never silently lossy.
HISTORICAL_HEADINGS = (
    "done",
    "completed",
    "complete",
    "finished",
    "shipped",
    "changelog",
    "change log",
    "history",
    "decision log",
    "decisions",
    "archive",
    "archived",
    "release notes",
    "retrospective",
    "postmortem",
    "work log",
)
# Whole-text (not substring) matches only, checked before the inline-marker
# regex below — "Nothing in progress" must not match on "in progress" and
# become a blocking row; it is evidence of nothing, not evidence of work.
EMPTY_MARKERS = frozenset(
    {
        "nothing in progress",
        "nothing",
        "none",
        "n/a",
        "na",
        "tbd",
        "empty",
        "no active work",
    }
)
INLINE_ACTIONABLE_RE = re.compile(
    r"(?<![A-Za-z])(todo|to-do|to do|fixme|xxx|hack|tbd|wip|blocked|blocker|"
    r"pending|not started|in progress|next step)(?![A-Za-z])",
    re.IGNORECASE,
)

HUMAN_SIGNOFF_ITEMS = (
    "The historical/reference sections listed by `migration-audit` were shown to the user",
    "Every migrated entry was checked for semantic equivalence against its destination",
    "The pointer audit passed: every live reference to the legacy source was updated",
    "The link audit passed: every changed relative link resolves",
    "The user chose whether to retain or delete the legacy source",
)

# --- Markdown lexing for the legacy-source scanner ---
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
ATX_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-*+]|\d+[.)])\s+(?P<body>.*)$")
CHECKBOX_RE = re.compile(r"^\[(?P<mark>[ xX])\]\s*(?P<body>.*)$")
TABLE_ROW_RE = re.compile(r"^\s*\|(?P<cells>.*)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
EMPHASIS_RE = re.compile(r"[*_`~]+")
LEADING_NUM_RE = re.compile(r"^\s*\d+[.)]\s*")
EDGE_JUNK_RE = re.compile(r"^[^\w]+|[^\w]+$")
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
HTML_COMMENT_START = "<!--"
HTML_COMMENT_END = "-->"


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

    inventory = commands.add_parser(
        "migration-inventory",
        help="Scan legacy source file(s) and write/refresh a migration inventory record.",
    )
    inventory.add_argument("slug", help="Kebab-case identifier for this migration.")
    inventory.add_argument(
        "--source",
        action="append",
        default=[],
        required=True,
        metavar="PATH",
        help=(
            "Legacy tracking file to inventory, relative to the project root. "
            "A directory is scanned recursively for *.md files. Repeat for multiple sources."
        ),
    )
    _location_args(inventory)

    audit = commands.add_parser(
        "migration-audit",
        help="Rescan the sources and reconcile against the migration record; the deletion gate.",
    )
    audit.add_argument("slug", help="Migration slug used by migration-inventory.")
    _location_args(audit)
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


# ---------------------------------------------------------------------------
# Migration inventory / audit
#
# See KNOWN-ISSUE.md KI-001. The scanner below inventories a legacy source
# whole-document: every section is classified `actionable`, `historical`, or
# — for anything neither list recognizes — `ambiguous`, which blocks the
# audit exactly like `actionable`. An unrecognized heading blocks by default
# instead of silently passing, which is what an empty "## Now" section did
# not do for a real "## Next steps" and backlog it never looked at.
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    t = LINK_RE.sub(r"\1", text)
    t = EMPHASIS_RE.sub("", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def normalize_key(text: str) -> str:
    """Aggressive normalization used for entry identity and empty-marker matching."""
    return _normalize_text(text)


def normalize_heading(title: str) -> str:
    t = LEADING_NUM_RE.sub("", title)
    t = _normalize_text(t)
    return EDGE_JUNK_RE.sub("", t)


def classify_heading(title: str) -> str:
    """Classify a heading as actionable, historical, or (default) ambiguous.

    Whole-token containment (padding both the title and each keyword with a
    space) avoids "backlog" matching inside an unrelated compound word while
    still matching "SEO backlog". When a heading matches both lists,
    actionable wins — the fail-safe direction.
    """
    padded = f" {normalize_heading(title)} "
    if any(f" {kw} " in padded for kw in ACTIONABLE_HEADINGS):
        return "actionable"
    if any(f" {kw} " in padded for kw in HISTORICAL_HEADINGS):
        return "historical"
    return "ambiguous"


def split_row(line: str) -> list[str]:
    """Split a rendered Markdown table row into its cell values.

    Cells are escaped by markdown_table_text()/markdown_code() (`|` -> `\\|`),
    so a naive split("|") would corrupt any cell containing a literal pipe.
    """
    return [c.strip() for c in CELL_SPLIT_RE.split(line.strip())[1:-1]]


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Yield (1-based lineno, line) pairs, with non-content regions removed.

    Strips a leading YAML front-matter block, fenced code regions, and HTML
    comments (all fail-safe: their content is invisible to the scanner, never
    misread as an entry). A single leading blockquote marker is stripped but
    its content kept — real content does live in blockquotes.
    """
    lines = text.splitlines()
    n = len(lines)
    start = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, n):
            if lines[j].strip() == "---":
                start = j + 1
                break

    result: list[tuple[int, str]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    in_comment = False
    for idx in range(start, n):
        raw = lines[idx]
        lineno = idx + 1
        if in_comment:
            if HTML_COMMENT_END in raw:
                in_comment = False
            continue
        if in_fence:
            m = FENCE_RE.match(raw)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                in_fence = False
            continue
        m = FENCE_RE.match(raw)
        if m:
            in_fence = True
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            continue
        stripped = raw.strip()
        if stripped.startswith(HTML_COMMENT_START):
            if HTML_COMMENT_END not in stripped:
                in_comment = True
            continue
        bq_match = re.match(r"^(\s{0,3})>\s?(.*)$", raw)
        line = bq_match.group(2) if bq_match else raw
        result.append((lineno, line))
    return result


@dataclass
class Section:
    level: int
    title: str
    path: str
    classification: str
    body: list[tuple[int, str]] = field(default_factory=list)


def parse_sections(text: str) -> list[Section]:
    """Split a document into sections, each running until the next heading of
    level <= its own. A subheading inherits its nearest ancestor's
    classification unless its own title classifies non-ambiguously — so an
    unrecognized "### Later" under an actionable "## Next steps" still blocks.
    """
    preamble = Section(level=0, title="(preamble)", path="(preamble)", classification="ambiguous")
    sections = [preamble]
    stack: list[Section] = []
    current = preamble

    for lineno, line in _logical_lines(text):
        m = ATX_RE.match(line)
        if not m:
            current.body.append((lineno, line))
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1].level >= level:
            stack.pop()
        own = classify_heading(title)
        inherited = stack[-1].classification if stack else "ambiguous"
        classification = own if own != "ambiguous" else inherited
        path = " > ".join([s.title for s in stack] + [title])
        section = Section(level=level, title=title, path=path, classification=classification)
        sections.append(section)
        stack.append(section)
        current = section

    return sections


@dataclass
class RawEntry:
    line: int
    text: str
    is_checkbox: bool
    checked: bool


def _iter_raw_entries(body: list[tuple[int, str]]) -> list[RawEntry]:
    """Extract list items, table data rows, and checkboxes from a section body.

    A checkbox is always its own entry regardless of nesting depth — the
    false-negative guard for a stray `- [ ]` left under a historical heading.
    A nested plain-text item folds into its top-level parent, mirroring the
    lazy-continuation semantics complete_tasks() already relies on elsewhere
    in this script.
    """
    n = len(body)
    entries: list[RawEntry] = []

    table_lines: set[int] = set()
    idx = 0
    while idx < n - 1:
        _, line = body[idx]
        _, next_line = body[idx + 1]
        if TABLE_ROW_RE.match(line) and TABLE_SEP_RE.match(next_line):
            table_lines.add(idx)
            table_lines.add(idx + 1)
            j = idx + 2
            while j < n and TABLE_ROW_RE.match(body[j][1]) and not TABLE_SEP_RE.match(body[j][1]):
                lineno, row = body[j]
                cells = split_row(row)
                text = next((c.strip() for c in cells if c.strip()), "")
                if text:
                    entries.append(RawEntry(lineno, text, False, False))
                table_lines.add(j)
                j += 1
            idx = j
        else:
            idx += 1

    pending_text: str | None = None
    pending_line = 0
    top_indent: int | None = None

    def flush() -> None:
        nonlocal pending_text, top_indent
        if pending_text is not None:
            entries.append(RawEntry(pending_line, pending_text.strip(), False, False))
        pending_text = None
        top_indent = None

    for idx in range(n):
        if idx in table_lines:
            flush()
            continue
        lineno, line = body[idx]
        m = LIST_RE.match(line)
        if m:
            indent = len(m.group("indent").expandtabs())
            item_body = m.group("body")
            cb = CHECKBOX_RE.match(item_body)
            if cb:
                flush()
                entries.append(
                    RawEntry(lineno, cb.group("body").strip(), True, cb.group("mark").lower() == "x")
                )
                continue
            if top_indent is None or indent <= top_indent:
                flush()
                top_indent = indent
                pending_text = item_body.strip()
                pending_line = lineno
            elif pending_text is not None:
                pending_text = f"{pending_text} {item_body.strip()}"
            continue
        if not line.strip():
            flush()
            continue
        if pending_text is not None and line[:1] in (" ", "\t"):
            pending_text = f"{pending_text} {line.strip()}"
            continue
        flush()

    flush()
    return entries


def entry_kind(entry: RawEntry, section_classification: str) -> str:
    """Resolve a raw entry's Kind. Order is load-bearing:

    checkbox state overrides everything (a stray `- [ ]` under `## Done` is
    still actionable); an exact empty-marker match must be checked before the
    inline-actionable regex, or "Nothing in progress" would match on
    "in progress" and become a blocking row.
    """
    if entry.is_checkbox:
        return "done" if entry.checked else "actionable"
    if normalize_key(entry.text) in EMPTY_MARKERS:
        return "empty"
    if INLINE_ACTIONABLE_RE.search(entry.text):
        return "actionable"
    if section_classification == "historical":
        return "historical"
    return section_classification  # actionable | ambiguous


def entry_identity(source_rel: str, section_path: str, text: str, occurrence: int) -> str:
    """A content-derived opaque ID, stable across reformatting.

    Keyed on normalized (source, section, text, occurrence) rather than line
    number, so a whitespace/marker-style edit elsewhere in the source does not
    silently re-key every row below it. If the entry's own text changes, its
    ID changes too — reported loudly (both an unaccounted source entry and a
    stale record row) rather than silently matched to the wrong row.
    """
    payload = "\x1f".join(
        [source_rel, normalize_key(section_path), normalize_key(text), str(occurrence)]
    )
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=4).hexdigest()
    return f"E{digest}"


@dataclass(frozen=True)
class SourceEntry:
    entry_id: str
    kind: str
    source: str
    line: int
    section: str
    text: str


def scan_source(text: str, source_rel: str) -> list[SourceEntry]:
    """Inventory every actionable/ambiguous/historical/done/empty entry in a
    legacy source document, whole-document — never scoped to a single
    "current work" section. Sections with no content at all (a bare title
    heading, an empty placeholder section) contribute nothing; there is
    nothing to lose by deleting a heading that never held any text.
    """
    sections = parse_sections(text)
    entries: list[SourceEntry] = []
    occurrence_counts: dict[tuple[str, str], int] = {}

    def make_entry(kind: str, entry_text: str, line: int, section_path: str) -> SourceEntry:
        key = (section_path, normalize_key(entry_text))
        occurrence = occurrence_counts.get(key, 0)
        occurrence_counts[key] = occurrence + 1
        entry_id = entry_identity(source_rel, section_path, entry_text, occurrence)
        return SourceEntry(
            entry_id=entry_id,
            kind=kind,
            source=source_rel,
            line=line,
            section=section_path,
            text=entry_text,
        )

    for section in sections:
        raw_entries = _iter_raw_entries(section.body)
        if not raw_entries:
            candidates = [(lineno, line.strip()) for lineno, line in section.body if line.strip()]
            if not candidates:
                continue
            lineno, first_line = candidates[0]
            raw_entries = [RawEntry(lineno, first_line, False, False)]

        kinds = [entry_kind(e, section.classification) for e in raw_entries]

        if section.classification == "historical":
            # Compress to one disclosure row per historical section; an entry
            # overridden to actionable/done by its own signal (a stray
            # checkbox, an inline TODO) stays individually visible.
            overridden = [(e, k) for e, k in zip(raw_entries, kinds) if k != "historical"]
            first_lineno = section.body[0][0] if section.body else 0
            entries.append(make_entry("historical", section.title, first_lineno, section.path))
            for e, k in overridden:
                entries.append(make_entry(k, e.text, e.line, section.path))
            continue

        for e, k in zip(raw_entries, kinds):
            entries.append(make_entry(k, e.text, e.line, section.path))

    return entries


def scan_relative_sources(
    rels: list[str], project_root: Path
) -> tuple[list[SourceEntry], dict[str, str | None]]:
    """Scan sources given as project-root-relative path strings.

    Returns every entry found in a still-readable source, and a digest dict
    mapping rel path -> SHA-256 hex digest, or None when the source can no
    longer be read (a legacy source the migration contract requires to stay
    byte-identical while the migration is open).
    """
    entries: list[SourceEntry] = []
    digests: dict[str, str | None] = {}
    for rel in rels:
        path = project_root / rel
        try:
            data = path.read_bytes()
        except OSError:
            digests[rel] = None
            continue
        digests[rel] = hashlib.sha256(data).hexdigest()
        entries.extend(scan_source(data.decode("utf-8"), rel))
    return entries, digests


def resolve_sources(raw_sources: list[str], project_root: Path, tracker_dir: Path) -> list[str]:
    """Validate --source arguments; return project-root-relative path strings.

    A directory source expands to every *.md file under it, recursively. A
    source may not resolve inside the tracker directory — a tracker item is
    a destination, never a legacy source to migrate from.
    """
    tracker_resolved = tracker_dir.resolve()
    root_resolved = project_root.resolve()
    rels: list[str] = []
    for raw in raw_sources:
        p = (project_root / raw).resolve()
        require_project_descendant(p, project_root, f"--source {raw}")
        if p == tracker_resolved or p.is_relative_to(tracker_resolved):
            sys.exit(f"ERROR: --source must not point inside the tracker directory: {p}")
        if p.is_dir():
            found = sorted(p.rglob("*.md"))
            if not found:
                sys.exit(f"ERROR: --source directory contains no Markdown files: {p}")
            rels.extend(f.relative_to(root_resolved).as_posix() for f in found)
        elif p.is_file():
            if p.suffix.lower() != ".md":
                sys.exit(f"ERROR: --source must be a Markdown (.md) file: {p}")
            rels.append(p.relative_to(root_resolved).as_posix())
        else:
            sys.exit(f"ERROR: --source not found: {p}")
    return rels


def migration_record_path(tracker_dir: Path, slug: str, project_root: Path) -> Path:
    path = tracker_dir / MIGRATIONS_DIRNAME / f"{slug}.md"
    require_project_descendant(path, project_root, "migration record")
    return path


def seed_migrations_readme(migrations_dir: Path) -> None:
    dest = migrations_dir / "README.md"
    if dest.exists():
        return
    migrations_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        (REFERENCES_DIR / "migrations-readme.md").read_text(encoding="utf-8"), encoding="utf-8"
    )


def render_entry_rows(entries: list[SourceEntry], preserved: dict[str, tuple[str, str]]) -> str:
    lines: list[str] = []
    for e in entries:
        disposition, destination = preserved.get(e.entry_id, _seed_cells(e.kind))
        entry_text = e.text if len(e.text) <= 160 else f"{e.text[:159]}…"
        cells = [
            e.entry_id,
            e.kind,
            markdown_code(e.source, table_cell=True),
            str(e.line) if e.line else "—",
            markdown_table_text(e.section),
            markdown_table_text(entry_text),
            disposition,
            markdown_table_text(destination),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _seed_cells(kind: str) -> tuple[str, str]:
    if kind in BLOCKING_KINDS:
        return TBD_CELL, TBD_CELL
    if kind == "historical":
        return "archived", "—"
    return "not-applicable", "—"  # done, empty


def render_migration_record(
    slug: str,
    created: str,
    updated: str,
    digests: dict[str, str | None],
    entries: list[SourceEntry],
    preserved: dict[str, tuple[str, str]],
) -> str:
    template = (REFERENCES_DIR / "MIGRATION.template.md").read_text(encoding="utf-8")
    source_rows = "\n".join(
        f"| {markdown_code(rel, table_cell=True)} | {digest or '—'} |"
        for rel, digest in sorted(digests.items())
    )
    entry_rows = render_entry_rows(entries, preserved)
    return (
        template.replace("{{SLUG}}", slug)
        .replace("{{CREATED}}", created)
        .replace("{{UPDATED}}", updated)
        .replace("{{SOURCE_ROWS}}", source_rows)
        .replace("{{ENTRY_ROWS}}", entry_rows)
    )


@dataclass
class RecordRow:
    entry_id: str
    kind: str
    source: str
    loc: str
    section: str
    text: str
    disposition: str
    destination: str


@dataclass
class MigrationRecord:
    sources: dict[str, str]
    rows: dict[str, RecordRow]
    signoff: dict[str, bool]


def _extract_block(text: str, start: str, end: str, path: Path) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        sys.exit(f"ERROR: migration record markers not found in {path}: {start} / {end}")
    return text[text.index(start) + len(start) : text.index(end)]


def parse_migration_record(text: str, path: Path) -> MigrationRecord:
    sources_block = _extract_block(text, MIGRATION_SOURCES_START, MIGRATION_SOURCES_END, path)
    table_block = _extract_block(text, MIGRATION_TABLE_START, MIGRATION_TABLE_END, path)
    signoff_block = _extract_block(text, MIGRATION_SIGNOFF_START, MIGRATION_SIGNOFF_END, path)

    sources: dict[str, str] = {}
    for line in sources_block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith(("|---", "| Source |")):
            continue
        cells = split_row(stripped)
        if len(cells) != 2:
            sys.exit(f"ERROR: malformed source row in {path}: {stripped!r}")
        sources[cells[0].strip("`")] = cells[1]

    rows: dict[str, RecordRow] = {}
    for line in table_block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith(("|---", "| ID |")):
            continue
        cells = split_row(stripped)
        if len(cells) != 8:
            sys.exit(f"ERROR: malformed entry row in {path}: {stripped!r}")
        entry_id, kind, source, loc, section, entry_text, disposition, destination = cells
        if entry_id in rows:
            sys.exit(f"ERROR: duplicate record row for {entry_id} in {path}")
        rows[entry_id] = RecordRow(
            entry_id=entry_id,
            kind=kind,
            source=source.strip("`"),
            loc=loc,
            section=section,
            text=entry_text,
            disposition=disposition,
            destination=destination,
        )

    signoff: dict[str, bool] = {}
    for line in signoff_block.splitlines():
        m = re.match(r"^-\s\[(?P<mark>[ xX])\]\s*(?P<label>.*)$", line.strip())
        if m:
            signoff[m.group("label").strip()] = m.group("mark").lower() == "x"

    return MigrationRecord(sources=sources, rows=rows, signoff=signoff)


def existing_item_slugs(tracker_dir: Path, project_root: Path) -> dict[str, Path]:
    slugs: dict[str, Path] = {}
    for progress_path in sorted(tracker_dir.glob("*/PROGRESS.md")):
        if progress_path.parent.name.startswith("_"):
            continue
        require_project_descendant(progress_path, project_root, "progress item")
        match = SLUG_LINE_RE.search(progress_path.read_text(encoding="utf-8"))
        if match:
            slugs[match.group(1).strip()] = progress_path
    return slugs


def reconcile(
    record: MigrationRecord,
    scanned: list[SourceEntry],
    digests: dict[str, str | None],
    tracker_dir: Path,
    project_root: Path,
) -> tuple[list[str], list[str]]:
    """Reconcile a migration record against a fresh scan. Returns
    (failures, historical-disclosure lines). Any failure keeps the deletion
    gate closed.
    """
    failures: list[str] = []

    for rel, recorded_digest in sorted(record.sources.items()):
        actual_digest = digests.get(rel)
        if actual_digest is None:
            failures.append(f"source no longer readable: {rel}")
        elif actual_digest != recorded_digest:
            failures.append(
                f"{rel}: source changed since the inventory was taken; "
                f"re-run migration-inventory to refresh the record"
            )

    scanned_by_id = {e.entry_id: e for e in scanned}

    for entry_id, entry in scanned_by_id.items():
        if entry_id not in record.rows:
            failures.append(
                f"{entry.source}:{entry.line}: unaccounted source entry "
                f"[{entry.kind}] '{entry.text}' (id={entry_id}); "
                f"re-run migration-inventory to add it"
            )

    for entry_id, row in record.rows.items():
        if entry_id not in scanned_by_id:
            failures.append(f"record row {entry_id} matches no source entry: '{row.text}'")

    historical: list[str] = []
    item_slugs = existing_item_slugs(tracker_dir, project_root)

    for entry_id, row in record.rows.items():
        entry = scanned_by_id.get(entry_id)
        if entry is None:
            continue  # already reported above

        if row.kind != entry.kind:
            failures.append(
                f"record row {entry_id}: Kind was hand-edited "
                f"(record={row.kind!r}, source={entry.kind!r})"
            )
            continue

        if row.kind == "historical":
            historical.append(f"{entry.source}:{entry.line}  {entry.section}")

        disposition = row.disposition.strip()
        destination = row.destination.strip()

        if row.kind in BLOCKING_KINDS and disposition in ("", TBD_CELL):
            failures.append(
                f"record row {entry_id} ({row.kind}) is unresolved: "
                f"{entry.source}:{entry.line} '{entry.text}' — set a Disposition and Destination"
            )
            continue

        if disposition in ("", TBD_CELL):
            continue  # non-blocking row left at its seeded default

        if disposition not in DISPOSITION_VALUES:
            failures.append(
                f"record row {entry_id}: unknown Disposition {disposition!r}; "
                f"expected one of {', '.join(DISPOSITION_VALUES)}"
            )
        elif disposition == "migrated":
            if destination in EMPTY_DESTINATION_VALUES:
                failures.append(
                    f"record row {entry_id}: Disposition 'migrated' requires a Destination item slug"
                )
            elif destination not in item_slugs:
                failures.append(
                    f"record row {entry_id}: destination {destination!r} is not an existing tracker item slug"
                )
        elif disposition == "excluded" and destination in EMPTY_DESTINATION_VALUES:
            failures.append(
                f"record row {entry_id}: Disposition 'excluded' requires a reason in Destination"
            )

    for label in HUMAN_SIGNOFF_ITEMS:
        if label not in record.signoff:
            failures.append(f"sign-off item missing from the record: {label!r}")
        elif not record.signoff[label]:
            failures.append(f"sign-off not confirmed: {label!r}")

    for failure in audit_tracker(tracker_dir, project_root):
        failures.append(f"tracker: {failure}")

    return failures, historical


def run_migration_inventory(args: argparse.Namespace) -> int:
    validate_slug(args.slug)
    project_root, tracker_dir, _ = resolve_location(args.root, args.dir)
    source_rels = resolve_sources(args.source, project_root, tracker_dir)
    entries, digests = scan_relative_sources(source_rels, project_root)
    unreadable = [rel for rel, digest in digests.items() if digest is None]
    if unreadable:
        sys.exit("ERROR: could not read source(s):\n  " + "\n  ".join(unreadable))
    if not entries:
        sys.exit(
            "ERROR: the source(s) produced no entries — check the path(s):\n  "
            + "\n  ".join(source_rels)
        )

    record_path = migration_record_path(tracker_dir, args.slug, project_root)
    before = record_path.read_text(encoding="utf-8") if record_path.is_file() else ""
    preserved: dict[str, tuple[str, str]] = {}
    dropped = 0
    created = date.today().isoformat()  # noqa: DTZ011
    prior_signoff: dict[str, bool] = {}
    if before:
        prior = parse_migration_record(before, record_path)
        created_match = CREATED_LINE_RE.search(before)
        if created_match:
            created = created_match.group(1).strip()
        scanned_ids = {e.entry_id for e in entries}
        preserved = {
            entry_id: (row.disposition, row.destination)
            for entry_id, row in prior.rows.items()
            if entry_id in scanned_ids and row.disposition not in ("", TBD_CELL)
        }
        dropped = len(set(prior.rows) - scanned_ids)
        prior_signoff = prior.signoff

    today = date.today().isoformat()  # noqa: DTZ011
    after = render_migration_record(args.slug, created, today, digests, entries, preserved)
    for label, checked in prior_signoff.items():
        if checked and label in HUMAN_SIGNOFF_ITEMS:
            after = after.replace(f"- [ ] {label}", f"- [x] {label}", 1)

    if args.dry_run:
        print_diff(record_path, before, after)
        print("[dry-run] No files written.")
        return 0

    record_path.parent.mkdir(parents=True, exist_ok=True)
    seed_migrations_readme(record_path.parent)
    record_path.write_text(after, encoding="utf-8")

    blocking = [e for e in entries if e.kind in BLOCKING_KINDS]
    print(f"{'Updated' if before else 'Created'}: {record_path}")
    print(f"Entries:  {len(entries)} total, {len(blocking)} needing a disposition")
    if before:
        print(f"Refresh:  {len(preserved)} preserved, {dropped} removed")
    for entry in blocking:
        print(f"  TBD  {entry.source}:{entry.line}  [{entry.section}]  {entry.text[:70]}")
    print()
    print("Next: fill in Disposition and Destination for every TBD row, tick the")
    print(f"      human sign-off boxes, then run: migration-audit {args.slug}")
    return 0


def run_migration_audit(args: argparse.Namespace) -> int:
    validate_slug(args.slug)
    project_root, tracker_dir, _ = resolve_location(args.root, args.dir)
    record_path = migration_record_path(tracker_dir, args.slug, project_root)
    if not record_path.is_file():
        sys.exit(
            f"ERROR: migration record not found: {record_path}\n"
            f"Run: update_progress.py migration-inventory {args.slug} --source <legacy-path>"
        )
    record = parse_migration_record(record_path.read_text(encoding="utf-8"), record_path)
    scanned, digests = scan_relative_sources(sorted(record.sources), project_root)
    failures, historical = reconcile(record, scanned, digests, tracker_dir, project_root)

    if historical:
        print("Historical / reference sections in the source (lost if the source is deleted):")
        for line in historical:
            print(f"  {line}")
    else:
        print("Historical / reference sections in the source: none")

    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        print(f"migration-audit: {len(failures)} problem(s) found")
        print("Deletion gate: CLOSED — the legacy source MUST NOT be deleted.")
        sys.exit("ERROR: migration-audit failed; migration is incomplete")

    blocking = sum(1 for row in record.rows.values() if row.kind in BLOCKING_KINDS)
    print(
        f"PASS  migration inventory reconciled: {blocking} actionable/ambiguous "
        f"entr(ies) resolved, {len(historical)} historical section(s) disclosed"
    )
    print("Deletion gate: OPEN — ask the user before deleting the legacy source.")
    return 0


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


COMMAND_HANDLERS = {
    "update": run_mutation,
    "close": run_mutation,
    "check": run_check,
    "migration-inventory": run_migration_inventory,
    "migration-audit": run_migration_audit,
}


def main() -> int:
    args = build_arg_parser().parse_args()
    return COMMAND_HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
