#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Create a new development progress item under a project's progress tracker.

The --scope argument accepts a comma-separated list of `name[:branch[:ticket]]`
entries, where:
  - name    a free-form label for the piece of work this item touches
            (a service, package, repo, component — whatever the project uses)
  - branch  git branch for this scope entry (optional, defaults to TBD)
  - ticket  issue/ticket reference for this scope entry — kept exactly as
            given (serial, #-prefixed, URL, Jira key, anything); optional,
            defaults to TBD

Usage:
    uv run new_progress.py <slug> --scope <entries> [options]

Examples:
    # Minimal — one scope entry, no branch or ticket yet
    uv run new_progress.py subscription-refund --scope api

    # Multiple scope entries with per-entry branches and tickets;
    # --ticket is the umbrella/epic reference for the whole task
    uv run new_progress.py subscription-refund \\
        --scope "api:feature/refund:JIRA-111,worker:feature/refund" \\
        --ticket EPIC-100 \\
        --plan ./my-plan.md \\
        --title "Refund flow rework"

    # Dry-run preview (no files written)
    uv run new_progress.py my-task --scope api --dry-run

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
                  linked via a relative path in PROGRESS.md.
                  - A path (absolute, or containing '/', or './'/'../') is
                    validated by existence directly.
                  - A bare filename (e.g. my-plan.md) is resolved against
                    $PROGRESS_TRACKER_PLANS_DIR, if that env var is set.
                    Without it, a bare filename is an error asking for a path.
    --title       Human-readable title. Defaults to the slug with hyphens
                  replaced by spaces and title-cased.
    --dir         Tracker directory name, relative to the project root.
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
    Copies:   <tracker-dir>/_plans/<plan-name>.md  (when --plan is given)
    Updates:  <tracker-dir>/INDEX.md  (appends a row to the item table)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

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


def parse_scope(scope_arg: str) -> list[ScopeEntry]:
    """Parse the --scope argument into a list of (name, branch, ticket) tuples.

    Each comma-separated entry has the form:  name[:branch[:ticket]]

    Rules:
      - name is a free-form label; not validated against any directory
      - branch defaults to 'TBD' when omitted or empty
      - ticket defaults to 'TBD' when omitted; kept verbatim otherwise
    """
    entries: list[ScopeEntry] = []

    for raw in scope_arg.split(","):
        raw = raw.strip()
        if not raw:
            continue
        # Split into at most 3 parts on ':'
        segments = raw.split(":", 2)
        name = segments[0].strip()
        branch = segments[1].strip() if len(segments) > 1 else ""
        ticket_raw = segments[2].strip() if len(segments) > 2 else ""

        if not name:
            sys.exit(f"ERROR: empty scope name in --scope entry: {raw!r}")

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
        if not p.exists():
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
    if candidate.exists():
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


def render_scope_rows(entries: list[ScopeEntry]) -> str:
    """Render the per-scope table rows for the ## Scope section."""
    lines: list[str] = []
    for name, branch, ticket in entries:
        branch_cell = f"`{branch}`" if branch != "TBD" else "TBD"
        lines.append(f"| `{name}` | {branch_cell} | {ticket} |  |")
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
    plan_display = f"../_plans/{plan_name}" if plan_name != "N/A" else "N/A"
    return (
        template
        .replace("{{TITLE}}", title)
        .replace("{{SLUG}}", slug)
        .replace("{{SCOPE_ROWS}}", scope_rows)
        .replace("{{TICKET}}", ticket)
        .replace("{{PLAN}}", plan_display)
        .replace("{{DATE}}", today)
    )


def scaffold_tracker_dir(tracker_dir: Path, dry_run: bool) -> None:
    """Create the tracker directory's supporting files on first use.

    Copies README.md, INDEX.md, _template/PROGRESS.md, and _plans/README.md
    from this skill's bundled references/ when they don't already exist.
    Never overwrites existing files.
    """
    seeds = [
        (REFERENCES_DIR / "tracker-readme.md", tracker_dir / "README.md"),
        (REFERENCES_DIR / "INDEX.template.md", tracker_dir / "INDEX.md"),
        (REFERENCES_DIR / "PROGRESS.template.md", tracker_dir / "_template" / "PROGRESS.md"),
        (REFERENCES_DIR / "plans-readme.md", tracker_dir / "_plans" / "README.md"),
    ]
    for source, dest in seeds:
        if dest.exists():
            continue
        if not source.exists():
            sys.exit(f"ERROR: bundled reference not found: {source}")
        if dry_run:
            print(f"[dry-run] Would scaffold: {dest}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            print(f"Scaffolded: {dest}")


def append_index_row(
    index_path: Path,
    tracker_dirname: str,
    folder_name: str,
    title: str,
    scope_entries: list[ScopeEntry],
    ticket: str,
    plan_name: str,
    today: str,
    dry_run: bool,
) -> None:
    index = index_path.read_text(encoding="utf-8")

    header_idx = index.find(TABLE_HEADER_MARKER)
    if header_idx == -1:
        sys.exit(
            f"ERROR: Could not find the table header marker in {index_path}.\n"
            f"Expected to find: {TABLE_HEADER_MARKER!r}"
        )

    # Skip past the header line and separator line to reach the first data row position
    after_header = index.find("\n", header_idx) + 1       # end of header line
    separator_end = index.find("\n", after_header) + 1    # end of separator line

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

    scope_display = ", ".join(f"`{name}`" for name, _, _ in scope_entries)
    # INDEX.md lives at the root of the tracker dir; _plans/ is a direct child.
    plan_display = f"_plans/{plan_name}" if plan_name != "N/A" else "N/A"
    new_row = (
        f"| `planning` | {title} | `{tracker_dirname}/{folder_name}/` | "
        f"{scope_display} | {ticket} | {plan_display} | {today} |  |\n"
    )

    updated = index[:table_end] + new_row + index[table_end:]

    if dry_run:
        print(f"[dry-run] Would append to {index_path}:")
        print(f"  {new_row.strip()}")
    else:
        index_path.write_text(updated, encoding="utf-8")
        print(f"Updated:  {index_path}")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a new development progress item under a project's progress tracker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run new_progress.py subscription-refund \\\n"
            '      --scope "api:feature/refund:JIRA-111,worker:feature/refund" \\\n'
            "      --ticket EPIC-100 --plan ./my-plan.md --title 'Refund flow rework'\n\n"
            "  uv run new_progress.py my-task --scope api --dry-run"
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
            "<tracker-dir>/_plans/ as a version-controlled snapshot."
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
            "Tracker directory name, relative to the project root. "
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
    scope_entries: list[ScopeEntry] = parse_scope(args.scope)
    ticket: str = normalize_ticket(args.ticket or "", default="N/A")
    plan_name: str
    source_path: Path | None
    plan_name, source_path = resolve_plan(args.plan)

    project_root = resolve_project_root(args.root)
    dirname = args.dir or os.environ.get("PROGRESS_TRACKER_DIR") or DEFAULT_TRACKER_DIRNAME
    tracker_dir = project_root / dirname
    template_path = tracker_dir / "_template" / "PROGRESS.md"
    index_path = tracker_dir / "INDEX.md"
    plans_local_dir = tracker_dir / "_plans"

    # --- Scaffold tracker dir on first use ---
    scaffold_tracker_dir(tracker_dir, dry_run)
    # In dry-run mode the scaffold files may not actually exist yet; use the
    # bundled reference directly so the preview can still render.
    if dry_run and not template_path.exists():
        template_path = REFERENCES_DIR / "PROGRESS.template.md"
    if dry_run and not index_path.exists():
        index_path = REFERENCES_DIR / "INDEX.template.md"

    # --- Build output path ---
    folder_name = f"{today}-{slug}"
    item_dir = tracker_dir / folder_name
    progress_file = item_dir / "PROGRESS.md"

    if item_dir.exists():
        sys.exit(
            f"ERROR: Directory already exists: {item_dir}\n"
            f"To avoid overwriting, this script will not proceed. "
            f"Choose a different slug or rename the existing folder."
        )

    rendered = render_template(template_path, title, slug, scope_entries, ticket, plan_name, today)

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

    append_index_row(
        index_path, dirname, folder_name, title, scope_entries, ticket, plan_name, today, dry_run
    )

    if not dry_run:
        print()
        print("Next steps:")
        print(f"  1. Open {progress_file}")
        print("     → Fill in Background & goals and Task list")
        print("  2. Back-fill TBD values in ## Scope as branches/tickets are created")
        print(f"  3. Update Status to `in-progress` in {index_path} when work begins")
        print("  4. After completing, fill in ## Outcome and update Status to `done` in INDEX.md")


if __name__ == "__main__":
    main()
