#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
r"""Create a new development progress item under a project's progress tracker.

The --scope argument accepts a comma-separated list of `name[:branch[:ticket]]`
entries, where:
  - name    a free-form label for the piece of work this item touches
            (a service, package, repo, component — whatever the project uses)
  - branch  git branch for this scope entry (optional, defaults to TBD)
  - ticket  issue/ticket reference for this scope entry — kept exactly as
            given (serial, #-prefixed, URL, Jira key, anything); optional,
            defaults to TBD

Escape literal delimiters and backslashes in any segment as `\,`, `\:`, and
`\\`. Unescaped commas separate entries; the first two unescaped colons in an
entry separate name, branch, and ticket.

Usage:
    uv run <skill-dir>/scripts/new_progress.py <slug> --scope <entries> [options]

Examples:
    # Minimal — one scope entry, no branch or ticket yet
    uv run <skill-dir>/scripts/new_progress.py subscription-refund --scope api

    # Multiple scope entries with per-entry branches and tickets;
    # --ticket is the umbrella/epic reference for the whole task
    uv run <skill-dir>/scripts/new_progress.py subscription-refund \\
        --scope "api:feature/refund:JIRA-111,worker:feature/refund" \\
        --ticket EPIC-100 \\
        --plan ./my-plan.md \\
        --title "Refund flow rework"

    # Dry-run preview (no files written)
    uv run <skill-dir>/scripts/new_progress.py my-task --scope api --dry-run

Arguments:
    slug          Kebab-case identifier for the task (e.g. subscription-refund).
                  Must match [a-z0-9][a-z0-9-]* — lowercase letters, digits, hyphens.

Options:
    --scope       Comma-separated `name[:branch[:ticket]]` entries. name is a
                  free-form label (not validated against any directory).
                  branch defaults to TBD when omitted.
                  ticket defaults to TBD when omitted; kept verbatim otherwise
                  (no normalization — pass whatever your tracker uses).
    --ticket      Umbrella/epic reference for the whole task (optional).
                  Kept verbatim. Defaults to N/A.
    --plan        Path to the associated plan file (optional but recommended
                  when a plan exists). The plan is copied into
                  <tracker-dir>/_plans/ as a version-controlled snapshot and
                  stored as <slug>-<plan-name> and linked via an explicit
                  relative Markdown link in PROGRESS.md.
                  - A path (absolute, or containing '/', or './'/'../') is
                    validated by existence directly.
                  - A bare filename (e.g. my-plan.md) is resolved against
                    $PROGRESS_TRACKER_PLANS_DIR, if that env var is set.
                    Without it, a bare filename is an error asking for a path.
    --title       Human-readable title. Defaults to the slug with hyphens
                  replaced by spaces and title-cased.
    --dir         Tracker directory path, relative to and strictly inside the
                  project root. Nested paths and dot-directories are allowed;
                  absolute paths, '.', '..', and symlink escapes are rejected.
                  Defaults to $PROGRESS_TRACKER_DIR, then "progress".
    --root        Project root directory. Defaults to the current git
                  repository's top level (`git rev-parse --show-toplevel`),
                  falling back to the current working directory when not
                  inside a git repository.
    --dry-run     Preview what would be created/changed without writing any files.

Output:
    Scaffolds (on first use): <tracker-dir>/{INDEX.md,README.md,
        _template/PROGRESS.md,_plans/README.md} from this skill's bundled
        references, if the tracker directory doesn't exist yet.
    Creates:  <tracker-dir>/YYYY-MM-DD-<slug>/PROGRESS.md
    Copies:   <tracker-dir>/_plans/<slug>-<plan-name>  (when --plan is given)
    Updates:  <tracker-dir>/INDEX.md  (appends a row to the item table)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# This script ships inside the skill (skills/progress-tracker/scripts/); the
# bundled reference templates it scaffolds from live as a sibling directory.
# Use .absolute() (not .resolve()) so a symlinked install still locates the
# bundled files correctly relative to the real script location.
SCRIPT_DIR: Path = Path(__file__).absolute().parent
REFERENCES_DIR: Path = SCRIPT_DIR.parent / "references"

DEFAULT_TRACKER_DIRNAME = "progress"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TABLE_HEADER_MARKER = "| Status | Item | Folder | Scope | Ticket | Plan | Created | Notes |"

# Type alias: (scope_name, branch, ticket)
ScopeEntry = tuple[str, str, str]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def validate_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        sys.exit(
            f"ERROR: slug must be lowercase letters, digits, and hyphens only "
            f"(e.g. subscription-refund). Got: {slug!r}"
        )


def resolve_project_root(root_arg: str | None) -> Path:
    """Resolve the project root.

    Precedence: --root argument > git repository top level > current
    working directory.
    """
    if root_arg:
        p = Path(root_arg).expanduser().absolute()
        if not p.is_dir():
            sys.exit(f"ERROR: --root is not a directory: {p}")
        return p
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def normalize_ticket(value: str, default: str = "N/A") -> str:
    """Normalize a ticket/issue reference.

    Kept verbatim — this script does not assume any particular tracker's
    numbering convention. Only trims whitespace and applies the default
    when empty.
    """
    v = value.strip() if value else ""
    return v if v else default


def validate_single_line(value: str, label: str) -> None:
    """Reject values that would inject additional Markdown lines."""
    if "\n" in value or "\r" in value:
        sys.exit(f"ERROR: {label} must be a single line")


def markdown_table_text(value: str) -> str:
    """Escape plain text for a GitHub-flavored Markdown table cell."""
    validate_single_line(value, "Markdown table value")
    return value.replace("\\", "\\\\").replace("|", "\\|")


def markdown_code(value: str, *, table_cell: bool = False) -> str:
    """Render a safe inline-code span, including values containing backticks."""
    validate_single_line(value, "inline-code value")
    rendered = value.replace("|", "\\|") if table_cell else value
    longest_run = max((len(run) for run in re.findall(r"`+", rendered)), default=0)
    delimiter = "`" * (longest_run + 1)
    padding = " " if longest_run else ""
    return f"{delimiter}{padding}{rendered}{padding}{delimiter}"


def markdown_link(label: str, target: str, *, table_cell: bool = False) -> str:
    """Render an explicit relative Markdown link with a URL-encoded target."""
    validate_single_line(label, "link label")
    validate_single_line(target, "link target")
    safe_label = label.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    if table_cell:
        safe_label = safe_label.replace("|", "\\|")
    return f"[{safe_label}]({quote(target, safe='/._-')})"


def snapshot_plan_name(slug: str, source_name: str) -> str:
    """Namespace a frozen plan snapshot by task slug to avoid basename collisions."""
    validate_single_line(source_name, "plan filename")
    return f"{slug}-{source_name}"


def parse_scope(scope_arg: str) -> list[ScopeEntry]:
    """Parse the --scope argument into a list of (name, branch, ticket) tuples.

    Each comma-separated entry has the form: name[:branch[:ticket]]. Literal
    commas, colons, and backslashes can be escaped with a backslash.

    Rules:
      - name is a free-form label; not validated against any directory
      - branch defaults to 'TBD' when omitted or empty
      - ticket defaults to 'TBD' when omitted; kept verbatim otherwise
    """
    entries: list[ScopeEntry] = []
    parsed_entries: list[list[str]] = []
    segments = [""]
    escaped = False

    for char in scope_arg:
        if escaped:
            if char not in {",", ":", "\\"}:
                sys.exit(
                    f"ERROR: unsupported --scope escape \\{char}; "
                    "only comma, colon, and backslash may be escaped"
                )
            segments[-1] += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ",":
            parsed_entries.append(segments)
            segments = [""]
        elif char == ":" and len(segments) < 3:
            segments.append("")
        else:
            segments[-1] += char

    if escaped:
        sys.exit("ERROR: --scope ends with an incomplete escape (trailing backslash)")
    parsed_entries.append(segments)

    for segments in parsed_entries:
        if len(segments) == 1 and not segments[0].strip():
            continue
        name = segments[0].strip()
        branch = segments[1].strip() if len(segments) > 1 else ""
        ticket_raw = segments[2].strip() if len(segments) > 2 else ""

        if not name:
            sys.exit(f"ERROR: empty scope name in --scope entry: {segments!r}")

        validate_single_line(name, "scope name")
        validate_single_line(branch, "scope branch")
        validate_single_line(ticket_raw, "scope ticket")

        branch = branch if branch else "TBD"
        ticket = normalize_ticket(ticket_raw, default="TBD")

        entries.append((name, branch, ticket))

    if not entries:
        sys.exit("ERROR: --scope produced no valid entries. Provide at least one scope name.")

    return entries


def resolve_plan(plan_arg: str | None) -> tuple[str, Path | None]:
    """Resolve a plan argument to (plan_name, source_path).

    Returns ("N/A", None) when no plan is specified.

    Accepts:
    - A path (absolute, or containing '/') — validated by existence directly.
      Works with plans from any agent or tool.
    - A bare filename (e.g. my-plan.md) — resolved against
      $PROGRESS_TRACKER_PLANS_DIR, if set. Without that env var, a bare
      filename is an error asking the caller to pass a path instead.
    """
    if not plan_arg:
        return "N/A", None
    p = Path(plan_arg).expanduser()
    # Path input: contains a separator or is absolute
    if "/" in plan_arg or p.is_absolute():
        if not p.is_file():
            sys.exit(f"ERROR: plan file not found: {p}")
        return p.name, p

    # Bare filename: only resolvable via $PROGRESS_TRACKER_PLANS_DIR
    plans_dir_env = os.environ.get("PROGRESS_TRACKER_PLANS_DIR")
    if not plans_dir_env:
        sys.exit(
            f"ERROR: {plan_arg!r} is a bare filename, but $PROGRESS_TRACKER_PLANS_DIR "
            f"is not set. Pass a path instead (e.g. ./{plan_arg} or an absolute path), "
            f"or set PROGRESS_TRACKER_PLANS_DIR to the directory that holds it."
        )
    plans_dir = Path(plans_dir_env).expanduser()
    candidate = plans_dir / p.name
    if candidate.is_file():
        return candidate.name, candidate

    available = sorted(f.name for f in plans_dir.glob("*.md")) if plans_dir.exists() else []
    close = difflib.get_close_matches(p.name, available, n=3, cutoff=0.4)
    lines = [f"ERROR: plan {p.name!r} not found in {plans_dir}"]
    if close:
        lines.append("  Closest matches:")
        for c in close:
            lines.append(f"    {c}")
    elif available:
        lines.append(f"  Available plans: {', '.join(available[:5])}")
    else:
        lines.append(f"  No plans found in {plans_dir}")
    lines.append("  → Fix the filename or pass a full path instead")
    sys.exit("\n".join(lines))


def copy_plan(source_path: Path, plan_name: str, plans_local_dir: Path, dry_run: bool) -> None:
    """Copy a plan file into the local _plans/ snapshot directory.

    Errors if the destination already exists (idempotency guard — avoids
    overwriting an existing frozen snapshot).
    """
    dest = plans_local_dir / plan_name
    if dest.exists():
        if dry_run:
            print(f"[dry-run] WARNING: plan snapshot already exists: {dest}")
            print("[dry-run]          Would not overwrite — remove manually if intended.")
            return
        sys.exit(
            f"ERROR: plan snapshot already exists: {dest}\n"
            f"To avoid overwriting an existing snapshot, this script will not proceed. "
            f"Remove the file manually if you intend to replace it."
        )
    if dry_run:
        print(f"[dry-run] Would copy plan: {source_path}")
        print(f"[dry-run]             to:  {dest}")
    else:
        plans_local_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)
        print(f"Copied:   {source_path.name} → {dest}")


def slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").title()


def require_project_descendant(path: Path, project_root: Path, label: str) -> None:
    """Require path to resolve strictly inside project_root.

    Resolving both paths catches an existing symlink that would otherwise
    redirect writes outside the project boundary.
    """
    root_resolved = project_root.resolve()
    path_resolved = path.resolve(strict=False)
    if path_resolved == root_resolved or not path_resolved.is_relative_to(root_resolved):
        sys.exit(
            f"ERROR: {label} must resolve inside the project root.\n"
            f"  Project root: {root_resolved}\n"
            f"  Resolved path: {path_resolved}"
        )


def resolve_tracker_dir(project_root: Path, dirname_arg: str) -> tuple[Path, str]:
    """Validate and resolve a project-relative tracker directory.

    Hidden and nested paths are allowed (for example, `.progress` and
    `docs/progress`). Absolute paths, the project root itself, parent
    traversal, and symlink escapes are rejected.
    """
    relative = Path(dirname_arg).expanduser()
    if relative.is_absolute():
        sys.exit(f"ERROR: --dir must be relative to the project root: {dirname_arg!r}")
    if relative == Path(".") or ".." in relative.parts:
        sys.exit(
            f"ERROR: --dir must name a directory inside the project root "
            f"(not '.' or a path containing '..'): {dirname_arg!r}"
        )

    normalized = relative.as_posix()
    tracker_dir = project_root / relative
    require_project_descendant(tracker_dir, project_root, "tracker directory")
    return tracker_dir, normalized


def render_scope_rows(entries: list[ScopeEntry]) -> str:
    """Render the per-scope table rows for the ## Scope section."""
    lines: list[str] = []
    for name, branch, ticket in entries:
        name_cell = markdown_code(name, table_cell=True)
        branch_cell = markdown_code(branch, table_cell=True) if branch != "TBD" else "TBD"
        ticket_cell = markdown_table_text(ticket)
        lines.append(f"| {name_cell} | {branch_cell} | {ticket_cell} |  |")
    return "\n".join(lines)


def render_template(
    template_path: Path,
    title: str,
    slug: str,
    scope_entries: list[ScopeEntry],
    ticket: str,
    plan_name: str,
    today: str,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    scope_rows = render_scope_rows(scope_entries)
    # PROGRESS.md lives one level inside the item folder; _plans/ is a sibling.
    plan_display = (
        markdown_link(plan_name, f"../_plans/{plan_name}") if plan_name != "N/A" else "N/A"
    )
    return (
        template
        .replace("{{TITLE}}", title)
        .replace("{{SLUG}}", slug)
        .replace("{{SCOPE_ROWS}}", scope_rows)
        .replace("{{TICKET}}", ticket)
        .replace("{{PLAN}}", plan_display)
        .replace("{{DATE}}", today)
    )


def scaffold_seeds(tracker_dir: Path) -> list[tuple[Path, Path]]:
    """Return bundled source/destination pairs for tracker support files."""
    return [
        (REFERENCES_DIR / "tracker-readme.md", tracker_dir / "README.md"),
        (REFERENCES_DIR / "INDEX.template.md", tracker_dir / "INDEX.md"),
        (REFERENCES_DIR / "PROGRESS.template.md", tracker_dir / "_template" / "PROGRESS.md"),
        (REFERENCES_DIR / "plans-readme.md", tracker_dir / "_plans" / "README.md"),
    ]


def validate_scaffold(tracker_dir: Path, project_root: Path) -> None:
    """Validate every scaffold source and destination before any writes."""
    for source, dest in scaffold_seeds(tracker_dir):
        require_project_descendant(dest, project_root, f"scaffold destination {dest}")
        if dest.is_symlink() and not dest.exists():
            sys.exit(f"ERROR: scaffold destination is a broken symlink: {dest}")
        if dest.exists() and not dest.is_file():
            sys.exit(f"ERROR: scaffold destination exists but is not a file: {dest}")
        if not dest.exists() and not source.is_file():
            sys.exit(f"ERROR: bundled reference not found: {source}")


def scaffold_tracker_dir(tracker_dir: Path, dry_run: bool) -> None:
    """Create the tracker directory's supporting files on first use.

    Copies README.md, INDEX.md, _template/PROGRESS.md, and _plans/README.md
    from this skill's bundled references/ when they don't already exist.
    Never overwrites existing files.
    """
    for source, dest in scaffold_seeds(tracker_dir):
        if dest.exists():
            continue
        if dry_run:
            print(f"[dry-run] Would scaffold: {dest}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            print(f"Scaffolded: {dest}")


def render_index_update(
    index: str,
    index_path: Path,
    tracker_dirname: str,
    folder_name: str,
    title: str,
    scope_entries: list[ScopeEntry],
    ticket: str,
    plan_name: str,
    today: str,
) -> tuple[str, str]:
    """Return the updated INDEX content and newly rendered row."""

    header_idx = index.find(TABLE_HEADER_MARKER)
    if header_idx == -1:
        sys.exit(
            f"ERROR: Could not find the table header marker in {index_path}.\n"
            f"Expected to find: {TABLE_HEADER_MARKER!r}"
        )

    # Skip past the header line and separator line to reach the first data row position.
    header_end = index.find("\n", header_idx)
    if header_end == -1:
        sys.exit(f"ERROR: Malformed item table in {index_path}: header has no separator row")
    after_header = header_end + 1
    separator_line_end = index.find("\n", after_header)
    if separator_line_end == -1 or not index[after_header:separator_line_end].startswith("|---"):
        sys.exit(f"ERROR: Malformed item table in {index_path}: separator row is missing")
    separator_end = separator_line_end + 1

    # Walk forward over all existing data rows (lines starting with "|")
    table_end = separator_end
    pos = separator_end
    while pos < len(index):
        line_end = index.find("\n", pos)
        if line_end == -1:
            # Last line with no trailing newline
            line = index[pos:]
            if line.startswith("|"):
                table_end = len(index)
            break
        line = index[pos:line_end]
        if line.startswith("|"):
            table_end = line_end + 1
            pos = line_end + 1
        else:
            break

    scope_display = ", ".join(markdown_code(name, table_cell=True) for name, _, _ in scope_entries)
    # INDEX.md lives at the root of the tracker dir; _plans/ is a direct child.
    plan_display = (
        markdown_link(plan_name, f"_plans/{plan_name}", table_cell=True)
        if plan_name != "N/A"
        else "N/A"
    )
    new_row = (
        f"| `planning` | {markdown_table_text(title)} | "
        f"{markdown_code(f'{tracker_dirname}/{folder_name}/', table_cell=True)} | "
        f"{scope_display} | {markdown_table_text(ticket)} | {plan_display} | {today} |  |\n"
    )

    updated = index[:table_end] + new_row + index[table_end:]

    return updated, new_row


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    script_display = f"{SCRIPT_DIR}/new_progress.py"
    parser = argparse.ArgumentParser(
        description="Create a new development progress item under a project's progress tracker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            f"  uv run {script_display} subscription-refund \\\n"
            '      --scope "api:feature/refund:JIRA-111,worker:feature/refund" \\\n'
            "      --ticket EPIC-100 --plan ./my-plan.md --title 'Refund flow rework'\n\n"
            f"  uv run {script_display} my-task --scope api --dry-run"
        ),
    )
    parser.add_argument(
        "slug",
        help=(
            "Kebab-case identifier for the task (e.g. subscription-refund). "
            "Allowed characters: lowercase letters, digits, hyphens."
        ),
    )
    parser.add_argument(
        "--scope",
        required=True,
        help=(
            "Comma-separated `name[:branch[:ticket]]` entries. "
            "name is a free-form label (service, package, repo — not validated). "
            "Escape literal commas, colons, and backslashes with a backslash. "
            "branch defaults to TBD when omitted. "
            "ticket defaults to TBD when omitted; kept verbatim otherwise."
        ),
    )
    parser.add_argument(
        "--ticket",
        default=None,
        metavar="TICKET",
        help="Umbrella/epic reference for the whole task (optional). Kept verbatim. Defaults to N/A.",
    )
    parser.add_argument(
        "--plan",
        default=None,
        metavar="PLAN",
        help=(
            "Path to the associated plan file (optional). A bare filename is "
            "resolved against $PROGRESS_TRACKER_PLANS_DIR if set, else it's an "
            "error — pass a path instead. The plan is copied into "
            "<tracker-dir>/_plans/ as a slug-namespaced version-controlled snapshot."
        ),
    )
    parser.add_argument(
        "--title",
        default=None,
        help=(
            "Human-readable title. Defaults to the slug with hyphens "
            "replaced by spaces and title-cased."
        ),
    )
    parser.add_argument(
        "--dir",
        default=None,
        metavar="DIRNAME",
        help=(
            "Tracker directory path, relative to and strictly inside the project root. "
            "Nested paths and dot-directories are allowed; absolute paths, '.', '..', "
            "and symlink escapes are rejected. "
            "Defaults to $PROGRESS_TRACKER_DIR, then 'progress'."
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        metavar="PATH",
        help=(
            "Project root directory. Defaults to the current git repository's "
            "top level, falling back to the current working directory."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created/changed without writing any files.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    slug: str = args.slug
    title: str = args.title if args.title else slug_to_title(slug)
    # Intentionally the local calendar date, not UTC: this dates a folder name
    # for the developer running the command, on their machine, right now.
    today: str = date.today().isoformat()  # noqa: DTZ011
    dry_run: bool = args.dry_run

    # --- Validate / parse ---
    validate_slug(slug)
    validate_single_line(title, "--title")
    scope_entries: list[ScopeEntry] = parse_scope(args.scope)
    ticket: str = normalize_ticket(args.ticket or "", default="N/A")
    validate_single_line(ticket, "--ticket")
    source_plan_name: str
    source_path: Path | None
    source_plan_name, source_path = resolve_plan(args.plan)
    plan_name = snapshot_plan_name(slug, source_plan_name) if source_path else "N/A"

    project_root = resolve_project_root(args.root)
    dirname_arg = args.dir or os.environ.get("PROGRESS_TRACKER_DIR") or DEFAULT_TRACKER_DIRNAME
    validate_single_line(dirname_arg, "--dir")
    tracker_dir, dirname = resolve_tracker_dir(project_root, dirname_arg)
    template_path = tracker_dir / "_template" / "PROGRESS.md"
    index_path = tracker_dir / "INDEX.md"
    plans_local_dir = tracker_dir / "_plans"

    # --- Build output path ---
    folder_name = f"{today}-{slug}"
    item_dir = tracker_dir / folder_name
    progress_file = item_dir / "PROGRESS.md"

    # --- Preflight every predictable failure before writing anything ---
    validate_scaffold(tracker_dir, project_root)
    for output_path, label in (
        (index_path, "INDEX.md"),
        (plans_local_dir, "plan snapshot directory"),
        (item_dir, "progress item directory"),
        (progress_file, "PROGRESS.md"),
    ):
        require_project_descendant(output_path, project_root, label)

    if item_dir.exists() or item_dir.is_symlink():
        sys.exit(
            f"ERROR: Directory already exists: {item_dir}\n"
            f"To avoid overwriting, this script will not proceed. "
            f"Choose a different slug or rename the existing folder."
        )

    if source_path:
        plan_dest = plans_local_dir / plan_name
        require_project_descendant(plan_dest, project_root, "plan snapshot")
        if plan_dest.exists() or plan_dest.is_symlink():
            sys.exit(
                f"ERROR: plan snapshot already exists: {plan_dest}\n"
                f"To avoid overwriting an existing snapshot, this script will not proceed. "
                f"Remove the file manually if you intend to replace it."
            )

    template_source = (
        template_path if template_path.is_file() else REFERENCES_DIR / "PROGRESS.template.md"
    )
    index_source = index_path if index_path.is_file() else REFERENCES_DIR / "INDEX.template.md"
    rendered = render_template(
        template_source, title, slug, scope_entries, ticket, plan_name, today
    )
    index_content = index_source.read_text(encoding="utf-8")
    updated_index, new_index_row = render_index_update(
        index_content,
        index_path,
        dirname,
        folder_name,
        title,
        scope_entries,
        ticket,
        plan_name,
        today,
    )

    # --- Scaffold tracker dir on first use, after preflight succeeds ---
    scaffold_tracker_dir(tracker_dir, dry_run)

    # --- Preview or write ---
    if dry_run:
        print(f"[dry-run] Would create: {item_dir}/")
        print(f"[dry-run] Would write:  {progress_file}")
        if source_path:
            print(f"[dry-run] Would copy plan: {source_path}")
            print(f"[dry-run]             to:  {plans_local_dir / plan_name}")
        print()
        print("-" * 60)
        print(rendered.rstrip())
        print("-" * 60)
        print()
    else:
        item_dir.mkdir(parents=True)
        progress_file.write_text(rendered, encoding="utf-8")
        print(f"Created:  {progress_file}")

    if source_path:
        copy_plan(source_path, plan_name, plans_local_dir, dry_run)

    if dry_run:
        print(f"[dry-run] Would append to {index_path}:")
        print(f"  {new_index_row.strip()}")
    else:
        index_path.write_text(updated_index, encoding="utf-8")
        print(f"Updated:  {index_path}")

    if not dry_run:
        print()
        print("Next steps:")
        print(f"  1. Open {progress_file}")
        print("     → Fill in Background & goals and Task list")
        print("  2. Back-fill TBD values in ## Scope as branches/tickets are created")
        print("  3. When status changes, update it in both PROGRESS.md and INDEX.md")
        print("  4. After completing, fill in ## Outcome and set both statuses to `done`")


if __name__ == "__main__":
    main()
