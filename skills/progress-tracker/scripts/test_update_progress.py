"""Unit and integration tests for update_progress.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent
NEW_SCRIPT = SCRIPTS_DIR / "new_progress.py"
UPDATE_SCRIPT = SCRIPTS_DIR / "update_progress.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("update_progress", UPDATE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register in sys.modules before exec: the module defines dataclasses, and
    # Python's dataclasses machinery resolves annotations via
    # sys.modules[cls.__module__] — without this, exec_module() raises.
    sys.modules["update_progress"] = module
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


up = _load_module()


def run_script(script: Path, args: list[str], cwd: Path):
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


@pytest.fixture
def project(tmp_path):
    init_git_repo(tmp_path)
    created = run_script(NEW_SCRIPT, ["demo-task", "--scope", "api"], tmp_path)
    assert created.returncode == 0, created.stderr
    return tmp_path


def item_file(project: Path) -> Path:
    return next((project / "progress").glob("*-demo-task/PROGRESS.md"))


class TestTransitions:
    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("planning", "in-progress"),
            ("planning", "abandoned"),
            ("in-progress", "review"),
            ("in-progress", "blocked"),
            ("blocked", "in-progress"),
            ("review", "in-progress"),
            ("review", "done"),
        ],
    )
    def test_allowed_transitions(self, current, target):
        up.validate_transition(current, target)

    @pytest.mark.parametrize(
        ("current", "target"),
        [("planning", "review"), ("planning", "done"), ("blocked", "done"), ("done", "review")],
    )
    def test_invalid_transitions(self, current, target):
        with pytest.raises(SystemExit):
            up.validate_transition(current, target)


class TestUpdateCommand:
    def test_updates_status_in_progress_and_index(self, project):
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--status", "in-progress"],
            project,
        )
        assert result.returncode == 0, result.stderr
        assert "**Status:** in-progress" in item_file(project).read_text()
        assert "| `in-progress` | Demo Task |" in (project / "progress" / "INDEX.md").read_text()

    def test_appends_work_log_without_status_change(self, project):
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--work-log", "Implemented validation."],
            project,
        )
        assert result.returncode == 0, result.stderr
        content = item_file(project).read_text()
        assert "- Implemented validation." in content
        assert f"**Updated:** {date.today().isoformat()}" in content  # noqa: DTZ011
        assert "**Status:** planning" in content

    def test_replaces_scope_table_with_escaped_values(self, project):
        result = run_script(
            UPDATE_SCRIPT,
            [
                "update",
                "demo-task",
                "--scope",
                r"api\,edge:feature/x:JIRA-1\,JIRA-2,worker",
            ],
            project,
        )
        assert result.returncode == 0, result.stderr
        content = item_file(project).read_text()
        assert "api,edge" in content
        assert "JIRA-1,JIRA-2" in content
        assert "`worker` | TBD | TBD" in content

    def test_scope_replacement_echoes_parsed_entries(self, project):
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--scope", "api:feature/x,worker"],
            project,
        )
        assert result.returncode == 0, result.stderr
        assert "Scope:   api · worker  (2 entries)" in result.stdout

    def test_ambiguous_scope_leaves_files_unchanged(self, project):
        before_progress = item_file(project).read_text()
        before_index = (project / "progress" / "INDEX.md").read_text()
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--scope", "api, worker"],
            project,
        )
        assert result.returncode != 0
        assert "ambiguous" in result.stderr
        assert item_file(project).read_text() == before_progress
        assert (project / "progress" / "INDEX.md").read_text() == before_index

    def test_empty_scope_entry_leaves_files_unchanged(self, project):
        before_progress = item_file(project).read_text()
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--scope", "api,"],
            project,
        )
        assert result.returncode != 0
        assert "empty --scope entry" in result.stderr
        assert item_file(project).read_text() == before_progress

    def test_dry_run_writes_nothing(self, project):
        before_progress = item_file(project).read_text()
        before_index = (project / "progress" / "INDEX.md").read_text()
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--status", "in-progress", "--dry-run"],
            project,
        )
        assert result.returncode == 0, result.stderr
        assert "[dry-run] No files written." in result.stdout
        assert item_file(project).read_text() == before_progress
        assert (project / "progress" / "INDEX.md").read_text() == before_index

    def test_invalid_transition_writes_nothing(self, project):
        before_progress = item_file(project).read_text()
        before_index = (project / "progress" / "INDEX.md").read_text()
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--status", "review"],
            project,
        )
        assert result.returncode != 0
        assert "invalid status transition" in result.stderr
        assert item_file(project).read_text() == before_progress
        assert (project / "progress" / "INDEX.md").read_text() == before_index

    def test_refuses_existing_status_drift(self, project):
        index = project / "progress" / "INDEX.md"
        index.write_text(index.read_text().replace("`planning`", "`blocked`", 1))
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--work-log", "Should not write."],
            project,
        )
        assert result.returncode != 0
        assert "status drift" in result.stderr
        assert "Should not write" not in item_file(project).read_text()

    def test_refuses_progress_symlink_escape(self, project, tmp_path):
        progress = item_file(project)
        outside = tmp_path.parent / f"outside-{tmp_path.name}.md"
        original = progress.read_text()
        outside.write_text(original)
        progress.unlink()
        progress.symlink_to(outside)
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--work-log", "Must stay contained."],
            project,
        )
        assert result.returncode != 0
        assert "must resolve inside the project root" in result.stderr
        assert outside.read_text() == original

    def test_requires_a_mutation(self, project):
        result = run_script(UPDATE_SCRIPT, ["update", "demo-task"], project)
        assert result.returncode != 0
        assert "requires at least one" in result.stderr

    def test_completes_an_exact_task_idempotently(self, project):
        progress = item_file(project)
        progress.write_text(
            progress.read_text().replace("- [ ]\n- [ ]", "- [ ] Add lifecycle command\n- [ ]")
        )
        first = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--complete-task", "Add lifecycle command"],
            project,
        )
        second = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--complete-task", "Add lifecycle command"],
            project,
        )
        assert first.returncode == second.returncode == 0
        assert "- [x] Add lifecycle command" in progress.read_text()

    def test_missing_task_refuses_without_writing(self, project):
        before = item_file(project).read_text()
        result = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--complete-task", "Does not exist"],
            project,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr
        assert item_file(project).read_text() == before

    def test_completes_wrapped_task_by_logical_text(self, project):
        progress = item_file(project)
        progress.write_text(
            progress.read_text().replace(
                "- [ ]\n- [ ]",
                "- [ ] Add validated update and close-out operations that keep\n"
                "  PROGRESS.md and INDEX.md synchronized.\n- [ ]",
            )
        )
        result = run_script(
            UPDATE_SCRIPT,
            [
                "update",
                "demo-task",
                "--complete-task",
                (
                    "Add validated update and close-out operations that keep "
                    "PROGRESS.md and INDEX.md synchronized."
                ),
            ],
            project,
        )
        assert result.returncode == 0, result.stderr
        assert "- [x] Add validated update" in progress.read_text()


class TestCloseCommand:
    def test_closes_review_item_as_done(self, project):
        first = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--status", "in-progress"],
            project,
        )
        second = run_script(
            UPDATE_SCRIPT,
            ["update", "demo-task", "--status", "review"],
            project,
        )
        closed = run_script(
            UPDATE_SCRIPT,
            [
                "close",
                "demo-task",
                "--outcome",
                "Shipped successfully.",
                "--pr",
                "PR #42",
                "--follow-up",
                "Monitor metrics.",
            ],
            project,
        )
        assert first.returncode == second.returncode == closed.returncode == 0
        content = item_file(project).read_text()
        assert "**Status:** done" in content
        assert "Shipped successfully." in content
        assert "**Final status:** done" in content
        assert "**PR / Commit:** PR #42" in content
        assert "**Follow-ups:** Monitor metrics." in content
        assert "Closed item as `done`." in content
        assert "| `done` | Demo Task |" in (project / "progress" / "INDEX.md").read_text()

    def test_can_abandon_from_planning(self, project):
        result = run_script(
            UPDATE_SCRIPT,
            ["close", "demo-task", "--status", "abandoned", "--outcome", "No longer needed."],
            project,
        )
        assert result.returncode == 0, result.stderr
        assert "**Status:** abandoned" in item_file(project).read_text()


class TestCheckCommand:
    def test_consistent_tracker_passes(self, project):
        result = run_script(UPDATE_SCRIPT, ["check"], project)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "PASS  tracker is consistent" in result.stdout

    def test_status_drift_fails(self, project):
        index = project / "progress" / "INDEX.md"
        index.write_text(index.read_text().replace("`planning`", "`blocked`", 1))
        result = run_script(UPDATE_SCRIPT, ["check"], project)
        assert result.returncode == 1
        assert "status drift" in result.stdout

    def test_stale_index_row_fails(self, project):
        item_file(project).unlink()
        result = run_script(UPDATE_SCRIPT, ["check"], project)
        assert result.returncode == 1
        assert "stale INDEX row" in result.stdout

    def test_missing_index_row_fails(self, project):
        index = project / "progress" / "INDEX.md"
        index.write_text("\n".join(line for line in index.read_text().splitlines() if "Demo Task" not in line) + "\n")
        result = run_script(UPDATE_SCRIPT, ["check"], project)
        assert result.returncode == 1
        assert "missing INDEX row" in result.stdout

    def test_duplicate_index_row_fails(self, project):
        index = project / "progress" / "INDEX.md"
        content = index.read_text()
        row = next(line for line in content.splitlines() if "Demo Task" in line)
        index.write_text(content.replace(row, f"{row}\n{row}"))
        result = run_script(UPDATE_SCRIPT, ["check"], project)
        assert result.returncode == 1
        assert "duplicate INDEX rows" in result.stdout

    def test_invalid_status_fails(self, project):
        progress = item_file(project)
        progress.write_text(progress.read_text().replace("**Status:** planning", "**Status:** mystery"))
        index = project / "progress" / "INDEX.md"
        index.write_text(index.read_text().replace("`planning`", "`mystery`", 1))
        result = run_script(UPDATE_SCRIPT, ["check"], project)
        assert result.returncode == 1
        assert "invalid status" in result.stdout

    def test_duplicate_slug_fails(self, project):
        created = run_script(NEW_SCRIPT, ["second-task", "--scope", "worker"], project)
        assert created.returncode == 0, created.stderr
        second = next((project / "progress").glob("*-second-task/PROGRESS.md"))
        second.write_text(second.read_text().replace("**Slug:** second-task", "**Slug:** demo-task"))
        result = run_script(UPDATE_SCRIPT, ["check"], project)
        assert result.returncode == 1
        assert "duplicate slug" in result.stdout

    def test_custom_tracker_dir(self, tmp_path):
        init_git_repo(tmp_path)
        created = run_script(
            NEW_SCRIPT,
            ["custom-task", "--scope", "api", "--dir", "dev-log"],
            tmp_path,
        )
        assert created.returncode == 0, created.stderr
        result = run_script(UPDATE_SCRIPT, ["check", "--dir", "dev-log"], tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Migration inventory / audit (KNOWN-ISSUE.md KI-001)
#
# A real migration trial treated an empty "## Now" section as proof a legacy
# source held no actionable content, while "## Next steps" and a backlog it
# never inspected still held unmigrated work. These tests pin the scanner's
# default-deny behavior and the audit's deletion gate.
# ---------------------------------------------------------------------------

LEGACY_SOURCE = """\
# Site progress

## Now

Nothing in progress

## Next steps

- Add sitemap.xml generation
- Wire up structured data

## SEO backlog

- [ ] Audit meta descriptions
- [x] Submit to Search Console

## Done

- Shipped the new landing page

## Decision log

- Chose Jekyll over Hugo
"""

SIGNOFF_LABELS = up.HUMAN_SIGNOFF_ITEMS


@pytest.fixture
def legacy(project):
    (project / "PROGRESS.md").write_text(LEGACY_SOURCE, encoding="utf-8")
    return project


def resolve_all_rows(record: Path, destination: str = "demo-task") -> None:
    tracker_dir = record.parents[1]
    destination_files = [
        path
        for path in tracker_dir.glob("*/PROGRESS.md")
        if f"**Slug:** {destination}" in path.read_text(encoding="utf-8")
    ]
    lines = record.read_text(encoding="utf-8").splitlines()
    anchors: list[str] = []
    for index, line in enumerate(lines):
        if "| TBD | TBD | TBD |" not in line:
            continue
        entry_id = up.split_row(line)[0]
        evidence = f"Migration evidence {len(anchors) + 1} for {entry_id}."
        anchors.append(evidence)
        lines[index] = line.replace(
            "| TBD | TBD | TBD |",
            f"| migrated | {destination} | {evidence} |",
            1,
        )
    if destination_files:
        destination_file = destination_files[0]
        destination_text = destination_file.read_text(encoding="utf-8")
        additions = [anchor for anchor in anchors if anchor not in destination_text]
        if additions:
            destination_file.write_text(
                destination_text + "\n" + "\n".join(additions) + "\n",
                encoding="utf-8",
            )
    record.write_text("\n".join(lines) + "\n", encoding="utf-8")


def migrated_evidence(record: Path) -> list[str]:
    return [
        up.unescape_table_text(up.split_row(line)[-1])
        for line in record.read_text(encoding="utf-8").splitlines()
        if line.startswith("|") and "| migrated |" in line
    ]


def tick_signoff(record: Path) -> None:
    text = record.read_text(encoding="utf-8")
    for label in SIGNOFF_LABELS:
        text = text.replace(f"- [ ] {label}", f"- [x] {label}")
    record.write_text(text, encoding="utf-8")


class TestMigrationScanner:
    def test_next_steps_bullets_are_actionable(self):
        entries = up.scan_source(LEGACY_SOURCE, "PROGRESS.md")
        next_steps = [e for e in entries if e.section.endswith("Next steps")]
        assert len(next_steps) == 2
        assert all(e.kind == "actionable" for e in next_steps)

    def test_now_nothing_in_progress_is_empty_not_actionable(self):
        entries = up.scan_source(LEGACY_SOURCE, "PROGRESS.md")
        now_entries = [e for e in entries if e.section.endswith("Now")]
        assert len(now_entries) == 1
        assert now_entries[0].kind == "empty"
        assert now_entries[0].kind not in up.BLOCKING_KINDS

    def test_unchecked_box_in_done_section_is_actionable(self):
        text = "## Done\n\n- Shipped v1\n- [ ] Backport the fix\n"
        entries = up.scan_source(text, "src.md")
        boxed = [e for e in entries if "Backport" in e.text]
        assert len(boxed) == 1
        assert boxed[0].kind == "actionable"

    def test_checked_box_is_done(self):
        entries = up.scan_source(LEGACY_SOURCE, "PROGRESS.md")
        checked = [e for e in entries if "Submit to Search Console" in e.text]
        assert len(checked) == 1
        assert checked[0].kind == "done"

    def test_unknown_heading_defaults_to_ambiguous(self):
        text = "## Random musings\n\n- Something unclassified\n"
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 1
        assert entries[0].kind == "ambiguous"
        assert entries[0].kind in up.BLOCKING_KINDS

    def test_known_historical_heading_emits_every_entry(self):
        text = "## Decision log\n\n- Chose A\n- Chose B\n- Chose C\n- Chose D\n- Chose E\n"
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 5
        assert all(entry.kind == "historical" for entry in entries)
        assert [entry.text for entry in entries] == [
            "Chose A",
            "Chose B",
            "Chose C",
            "Chose D",
            "Chose E",
        ]

    def test_heading_matching_both_lists_resolves_actionable(self):
        text = "## Completed tasks\n\n- Ship the thing\n"
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 1
        assert entries[0].kind == "actionable"

    def test_nested_checkbox_becomes_its_own_entry(self):
        text = "## Next steps\n\n- Parent item\n  - [ ] Child sub-task\n"
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 2
        assert any(e.text == "Child sub-task" and e.kind == "actionable" for e in entries)

    def test_nested_plain_bullet_folds_into_parent(self):
        text = "## Next steps\n\n- Parent item\n  - a clarifying detail\n"
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 1
        assert "a clarifying detail" in entries[0].text

    def test_lazy_continuation_folds_into_parent(self):
        text = "## Next steps\n\n- Parent item continues\n  onto the next line\n"
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 1
        assert "onto the next line" in entries[0].text

    def test_code_fence_content_is_ignored(self):
        text = "## Next steps\n\n```\n- [ ] not a real task\n```\n"
        entries = up.scan_source(text, "src.md")
        assert entries == []

    def test_html_comment_content_is_ignored(self):
        text = "## Next steps\n\n<!-- - [ ] commented out -->\n"
        entries = up.scan_source(text, "src.md")
        assert entries == []

    def test_heading_scope_ends_at_same_or_higher_level(self):
        text = "## Next steps\n\n### Later\n\n- deferred item\n\n## Done\n\n- shipped\n"
        entries = up.scan_source(text, "src.md")
        deferred = next(e for e in entries if "deferred item" in e.text)
        assert deferred.kind == "actionable"
        done = next(e for e in entries if e.kind == "historical")
        assert "Done" in done.section

    def test_subheading_inherits_parent_classification(self):
        text = "## Next steps\n\n### Later\n\n- deferred item\n"
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 1
        assert entries[0].kind == "actionable"

    def test_table_data_row_in_actionable_section_is_an_entry(self):
        text = "## Backlog\n\n| Task | Status |\n|---|---|\n| Fix X | open |\n| Fix Y | open |\n"
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 2
        assert {e.text for e in entries} == {
            "Task=Fix X; Status=open",
            "Task=Fix Y; Status=open",
        }

    def test_table_row_retains_every_semantic_cell(self):
        text = (
            "## Feature list\n\n"
            "| # | Behavior | Verify with | State |\n"
            "|---|---|---|---|\n"
            "| 1 | Build every page | `npm test` | passing |\n"
        )
        entries = up.scan_source(text, "src.md")
        assert len(entries) == 1
        assert entries[0].text == (
            "#=1; Behavior=Build every page; Verify with=`npm test`; State=passing"
        )

    def test_mixed_prose_list_and_table_are_all_inventoried_in_source_order(self):
        text = (
            "## Next steps\n\n"
            "Context explaining why the work remains.\n\n"
            "- Implement the first task\n\n"
            "| Task | State |\n|---|---|\n| Implement the second task | open |\n\n"
            "Test constraint: update the matching assertion.\n"
        )
        entries = up.scan_source(text, "src.md")
        assert [e.text for e in entries] == [
            "Context explaining why the work remains.",
            "Implement the first task",
            "Task=Implement the second task; State=open",
            "Test constraint: update the matching assertion.",
        ]

    def test_multiline_prose_is_one_complete_entry(self):
        text = "## Backlog\n\nFirst line of context\ncontinues on the second line.\n"
        entries = up.scan_source(text, "src.md")
        assert [e.text for e in entries] == [
            "First line of context continues on the second line."
        ]

    def test_punctuated_none_currently_open_is_empty(self):
        entries = up.scan_source("## Blockers\n\nNone currently open.\n", "src.md")
        assert len(entries) == 1
        assert entries[0].kind == "empty"

    def test_preamble_is_ambiguous(self):
        text = "Some intro prose with no heading yet.\n\n## Done\n\n- shipped\n"
        entries = up.scan_source(text, "src.md")
        preamble = next(e for e in entries if e.section == "(preamble)")
        assert preamble.kind == "ambiguous"

    def test_entry_id_is_stable_across_reformatting(self):
        a = up.scan_source("## Next steps\n\n- Add sitemap.xml generation\n", "src.md")
        b = up.scan_source("## Next steps\n\n*   **Add sitemap.xml generation**\n", "src.md")
        assert a[0].entry_id == b[0].entry_id

    def test_entry_id_disambiguates_duplicate_text(self):
        entries = up.scan_source("## Next steps\n\n- Same text\n- Same text\n", "src.md")
        assert len({e.entry_id for e in entries}) == 2

    def test_entry_id_changes_when_text_changes(self):
        a = up.scan_source("## Next steps\n\n- Original text\n", "src.md")
        b = up.scan_source("## Next steps\n\n- Edited text\n", "src.md")
        assert a[0].entry_id != b[0].entry_id


class TestMigrationInventoryCommand:
    def test_first_inventory_scaffolds_tracker_before_any_item_exists(self, tmp_path):
        init_git_repo(tmp_path)
        (tmp_path / "PROGRESS.md").write_text(LEGACY_SOURCE)
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "progress" / "README.md").is_file()
        assert (tmp_path / "progress" / "INDEX.md").is_file()
        assert (tmp_path / "progress" / "_template" / "PROGRESS.md").is_file()
        assert (tmp_path / "progress" / "_plans" / "README.md").is_file()
        assert (tmp_path / "progress" / "_migrations" / "legacy-progress.md").is_file()
        assert not list((tmp_path / "progress").glob("*-demo-task"))

    def test_first_inventory_dry_run_does_not_scaffold_tracker(self, tmp_path):
        init_git_repo(tmp_path)
        (tmp_path / "PROGRESS.md").write_text(LEGACY_SOURCE)
        result = run_script(
            UPDATE_SCRIPT,
            [
                "migration-inventory",
                "legacy-progress",
                "--source",
                "PROGRESS.md",
                "--dry-run",
            ],
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert "[dry-run] Would scaffold:" in result.stdout
        assert not (tmp_path / "progress").exists()

    def test_creates_record_with_every_actionable_entry(self, legacy):
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        record = legacy / "progress" / "_migrations" / "legacy-progress.md"
        content = record.read_text()
        assert content.count("| TBD | TBD | TBD |") == 3
        assert "Add sitemap.xml generation" in content
        assert "Wire up structured data" in content
        assert "Audit meta descriptions" in content

    def test_seeds_non_blocking_rows_without_tbd(self, legacy):
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        content = (legacy / "progress" / "_migrations" / "legacy-progress.md").read_text()
        assert "| not-applicable | — | — |" in content  # `empty`/`done` rows
        assert "| archived |" not in content

    def test_record_does_not_truncate_long_entries(self, legacy):
        long_task = "A" * 240
        (legacy / "PROGRESS.md").write_text(f"## Next steps\n\n- {long_task}\n")
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        content = (legacy / "progress" / "_migrations" / "legacy-progress.md").read_text()
        assert long_task in content
        assert f"{'A' * 159}…" not in content

    def test_refuses_source_outside_project_root(self, legacy, tmp_path):
        outside = tmp_path.parent / "outside.md"
        outside.write_text("## Next steps\n\n- x\n")
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "../outside.md"],
            legacy,
        )
        assert result.returncode != 0
        assert "must resolve inside the project root" in result.stderr

    def test_refuses_source_inside_tracker_dir(self, legacy):
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "progress/INDEX.md"],
            legacy,
        )
        assert result.returncode != 0
        assert "must not point inside the tracker directory" in result.stderr

    def test_refuses_source_with_no_entries(self, legacy):
        (legacy / "empty.md").write_text("# Title\n")
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "empty.md"],
            legacy,
        )
        assert result.returncode != 0
        assert "produced no entries" in result.stderr

    def test_refuses_invalid_slug(self, legacy):
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "Bad_Slug", "--source", "PROGRESS.md"],
            legacy,
        )
        assert result.returncode != 0

    def test_dry_run_writes_nothing(self, legacy):
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md", "--dry-run"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        assert "[dry-run] No files written." in result.stdout
        assert not (legacy / "progress" / "_migrations").exists()

    def test_rerun_preserves_filled_dispositions(self, legacy):
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        record = legacy / "progress" / "_migrations" / "legacy-progress.md"
        resolve_all_rows(record)
        (legacy / "PROGRESS.md").write_text(
            LEGACY_SOURCE.replace(
                "- Wire up structured data\n",
                "- Wire up structured data\n- Add a robots.txt entry\n",
            )
        )
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        assert "Refresh:  7 preserved, 0 removed" in result.stdout
        content = record.read_text()
        assert content.count("| migrated | demo-task | Migration evidence ") == 3
        assert "| TBD | TBD | TBD |" in content  # the newly added entry

    def test_rerun_resets_signoffs_when_inventory_changes(self, legacy):
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        record = legacy / "progress" / "_migrations" / "legacy-progress.md"
        tick_signoff(record)
        (legacy / "PROGRESS.md").write_text(
            LEGACY_SOURCE.replace(
                "- Wire up structured data\n",
                "- Wire up structured data\n- Add a robots.txt entry\n",
            )
        )
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        assert "Sign-offs: reset — inventory changed" in result.stdout
        content = record.read_text()
        assert "- [x]" not in content
        assert content.count("- [ ]") == len(SIGNOFF_LABELS)

    def test_rerun_preserves_signoffs_only_when_inventory_is_identical(self, legacy):
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        record = legacy / "progress" / "_migrations" / "legacy-progress.md"
        tick_signoff(record)
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        assert "Sign-offs: preserved" in result.stdout
        assert record.read_text().count("- [x]") == len(SIGNOFF_LABELS)

    def test_rerun_drops_removed_disposition_and_resets_signoffs(self, legacy):
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        record = legacy / "progress" / "_migrations" / "legacy-progress.md"
        text = record.read_text().replace(
            "| not-applicable | — | — |", "| archived | — | — |", 1
        )
        record.write_text(text)
        tick_signoff(record)
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        assert "Sign-offs: reset — inventory changed" in result.stdout
        content = record.read_text()
        assert "| archived |" not in content
        assert "- [x]" not in content

    def test_rerun_drops_vanished_rows(self, legacy):
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        (legacy / "PROGRESS.md").write_text(
            LEGACY_SOURCE.replace("- Wire up structured data\n", "")
        )
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        content = (legacy / "progress" / "_migrations" / "legacy-progress.md").read_text()
        assert "Wire up structured data" not in content

    def test_directory_source_is_scanned_recursively(self, legacy):
        nested = legacy / "notes" / "sub"
        nested.mkdir(parents=True)
        (nested / "todo.md").write_text("## Next steps\n\n- Nested task\n")
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "notes"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        content = (legacy / "progress" / "_migrations" / "legacy-progress.md").read_text()
        assert "Nested task" in content

    def test_migrations_dir_is_ignored_by_check(self, legacy):
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        result = run_script(UPDATE_SCRIPT, ["check"], legacy)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_refresh_upgrades_v1_to_v2_preserves_choices_and_resets_signoffs(self, legacy):
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        record = legacy / "progress" / "_migrations" / "legacy-progress.md"
        resolve_all_rows(record)
        tick_signoff(record)
        lines = record.read_text(encoding="utf-8").splitlines()
        v1_lines: list[str] = []
        in_outcome = False
        in_entries = False
        for line in lines:
            if line == "**Schema version:** 2":
                continue
            if line == up.MIGRATION_OUTCOME_START:
                in_outcome = True
                continue
            if in_outcome:
                if line == up.MIGRATION_OUTCOME_END:
                    in_outcome = False
                continue
            if line == up.MIGRATION_TABLE_START:
                in_entries = True
            elif line == up.MIGRATION_TABLE_END:
                in_entries = False
            if in_entries and line.startswith("|"):
                cells = up.split_row(line)
                if len(cells) == 9:
                    line = "| " + " | ".join(cells[:8]) + " |"
            v1_lines.append(line)
        record.write_text("\n".join(v1_lines) + "\n", encoding="utf-8")

        result = run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        assert result.returncode == 0, result.stderr
        assert "Schema:   1 → 2" in result.stdout
        content = record.read_text(encoding="utf-8")
        assert "**Schema version:** 2" in content
        assert content.count("| migrated | demo-task | TBD |") == 3
        assert "- [x]" not in content


class TestMigrationAuditCommand:
    def _inventory(self, legacy: Path) -> Path:
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        return legacy / "progress" / "_migrations" / "legacy-progress.md"

    def test_fails_while_next_steps_unresolved_though_now_is_empty(self, legacy):
        self._inventory(legacy)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "is unresolved" in result.stdout
        assert "migration-audit failed" in result.stderr
        assert "Deletion gate: CLOSED" in result.stdout

    def test_fails_when_record_missing(self, legacy):
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "migration record not found" in result.stderr

    def test_fails_when_ambiguous_entry_unclassified(self, legacy):
        (legacy / "PROGRESS.md").write_text("## Random musings\n\n- Something unclassified\n")
        record = self._inventory(legacy)
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "(ambiguous) is unresolved" in result.stdout

    def test_fails_when_migrated_row_has_no_destination(self, legacy):
        record = self._inventory(legacy)
        text = record.read_text().replace("| TBD | TBD | TBD |", "| migrated | TBD | TBD |")
        record.write_text(text)
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "requires a Destination" in result.stdout

    def test_fails_when_excluded_row_has_no_reason(self, legacy):
        record = self._inventory(legacy)
        text = record.read_text().replace("| TBD | TBD | TBD |", "| excluded | — | — |")
        record.write_text(text)
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "requires a reason" in result.stdout

    def test_fails_when_destination_slug_does_not_exist(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record, destination="ghost-item")
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "not an existing tracker item slug" in result.stdout

    def test_fails_when_migrated_evidence_is_missing(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        evidence = migrated_evidence(record)[0]
        record.write_text(record.read_text().replace(evidence, "TBD", 1))
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "requires Evidence" in result.stdout

    def test_fails_when_migrated_evidence_is_not_in_destination(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        evidence = migrated_evidence(record)[0]
        record.write_text(record.read_text().replace(evidence, "Missing destination locator", 1))
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "was not found" in result.stdout

    def test_fails_when_migrated_evidence_is_not_unique(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        progress = item_file(legacy)
        evidence = migrated_evidence(record)[0]
        progress.write_text(progress.read_text() + f"\n{evidence}\n")
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "is not unique" in result.stdout

    def test_fails_when_two_rows_reuse_one_destination_locator(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        evidence = migrated_evidence(record)
        record.write_text(record.read_text().replace(evidence[1], evidence[0], 1))
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "each migrated row requires its own locator" in result.stdout

    def test_fails_when_kind_edited_by_hand(self, legacy):
        record = self._inventory(legacy)
        text = record.read_text().replace(
            "| actionable | `PROGRESS.md` | 9 |", "| historical | `PROGRESS.md` | 9 |"
        )
        record.write_text(text)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "generated field(s) were hand-edited: Kind" in result.stdout

    @pytest.mark.parametrize(
        ("old", "new", "field"),
        [
            (
                "| actionable | `PROGRESS.md` | 9 |",
                "| actionable | `OTHER.md` | 9 |",
                "Source",
            ),
            ("Site progress > Next steps", "Site progress > Later", "Section"),
            ("Add sitemap.xml generation", "Add robots.txt generation", "Entry"),
        ],
    )
    def test_fails_when_generated_field_edited_by_hand(self, legacy, old, new, field):
        record = self._inventory(legacy)
        text = record.read_text()
        assert old in text
        record.write_text(text.replace(old, new, 1))
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert f"generated field(s) were hand-edited: {field}" in result.stdout

    def test_fails_when_blocking_row_uses_not_applicable(self, legacy):
        record = self._inventory(legacy)
        text = record.read_text().replace(
            "| TBD | TBD | TBD |", "| not-applicable | — | — |"
        )
        record.write_text(text)
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "is not allowed for Kind 'actionable'" in result.stdout

    def test_fails_when_removed_archived_disposition_is_used(self, legacy):
        record = self._inventory(legacy)
        text = record.read_text().replace(
            "| not-applicable | — | — |", "| archived | — | — |", 1
        )
        record.write_text(text)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "unknown Disposition 'archived'" in result.stdout

    def test_fails_when_source_gains_a_new_entry(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        tick_signoff(record)
        (legacy / "PROGRESS.md").write_text(
            LEGACY_SOURCE.replace(
                "- Wire up structured data\n",
                "- Wire up structured data\n- A brand new task\n",
            )
        )
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "unaccounted source entry" in result.stdout

    def test_fails_when_source_changed_after_inventory(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        tick_signoff(record)
        (legacy / "PROGRESS.md").write_text(LEGACY_SOURCE + "\n")
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "source changed since the inventory" in result.stdout

    def test_fails_when_signoff_boxes_unticked(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "sign-off not confirmed" in result.stdout

    def test_fails_when_tracker_inconsistent(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        tick_signoff(record)
        index = legacy / "progress" / "INDEX.md"
        index.write_text(index.read_text().replace("`planning`", "`blocked`", 1))
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode != 0
        assert "tracker: " in result.stdout

    def test_passes_when_every_entry_resolved_and_signed_off(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        tick_signoff(record)
        result = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Pre-deletion gate: OPEN" in result.stdout
        assert "user chose whether" not in record.read_text().lower()

    def test_prints_historical_disclosure_on_pass_and_fail(self, legacy):
        record = self._inventory(legacy)
        failing = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert "Decision log" in failing.stdout
        resolve_all_rows(record)
        tick_signoff(record)
        passing = run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert "Decision log" in passing.stdout
        assert "Decision log: 1 entr(ies)" in passing.stdout

    def test_custom_tracker_dir(self, tmp_path):
        init_git_repo(tmp_path)
        created = run_script(NEW_SCRIPT, ["demo-task", "--scope", "api", "--dir", "dev-log"], tmp_path)
        assert created.returncode == 0, created.stderr
        (tmp_path / "PROGRESS.md").write_text(LEGACY_SOURCE, encoding="utf-8")
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md", "--dir", "dev-log"],
            tmp_path,
        )
        record = tmp_path / "dev-log" / "_migrations" / "legacy-progress.md"
        resolve_all_rows(record)
        tick_signoff(record)
        result = run_script(
            UPDATE_SCRIPT, ["migration-audit", "legacy-progress", "--dir", "dev-log"], tmp_path
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_audit_writes_nothing(self, legacy):
        record = self._inventory(legacy)
        resolve_all_rows(record)
        tick_signoff(record)
        before = record.read_text()
        run_script(UPDATE_SCRIPT, ["migration-audit", "legacy-progress"], legacy)
        assert record.read_text() == before


class TestMigrationFinalizeCommand:
    def _prepared_record(self, legacy: Path) -> Path:
        run_script(
            UPDATE_SCRIPT,
            ["migration-inventory", "legacy-progress", "--source", "PROGRESS.md"],
            legacy,
        )
        record = legacy / "progress" / "_migrations" / "legacy-progress.md"
        resolve_all_rows(record)
        tick_signoff(record)
        return record

    def test_records_retained_without_deleting_source(self, legacy):
        record = self._prepared_record(legacy)
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-finalize", "legacy-progress", "--decision", "retain"],
            legacy,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (legacy / "PROGRESS.md").is_file()
        content = record.read_text(encoding="utf-8")
        assert "**State:** retained" in content
        assert f"**Decision date:** {date.today().isoformat()}" in content  # noqa: DTZ011
        assert "The legacy source(s) remain retained" in result.stdout

    def test_delete_approval_is_non_destructive(self, legacy):
        record = self._prepared_record(legacy)
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-finalize", "legacy-progress", "--decision", "delete"],
            legacy,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (legacy / "PROGRESS.md").is_file()
        assert "**State:** delete-approved" in record.read_text(encoding="utf-8")
        assert "No source files were deleted" in result.stdout

    def test_refuses_confirmation_while_an_approved_source_exists(self, legacy):
        self._prepared_record(legacy)
        run_script(
            UPDATE_SCRIPT,
            ["migration-finalize", "legacy-progress", "--decision", "delete"],
            legacy,
        )
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-finalize", "legacy-progress", "--confirm-deleted"],
            legacy,
        )
        assert result.returncode != 0
        assert "still exist" in result.stderr

    def test_confirms_deleted_only_after_source_is_absent(self, legacy):
        record = self._prepared_record(legacy)
        run_script(
            UPDATE_SCRIPT,
            ["migration-finalize", "legacy-progress", "--decision", "delete"],
            legacy,
        )
        (legacy / "PROGRESS.md").unlink()
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-finalize", "legacy-progress", "--confirm-deleted"],
            legacy,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        content = record.read_text(encoding="utf-8")
        assert "**State:** deleted" in content
        assert f"**Completion date:** {date.today().isoformat()}" in content  # noqa: DTZ011

    def test_refuses_confirmation_if_record_changed_after_approval(self, legacy):
        record = self._prepared_record(legacy)
        run_script(
            UPDATE_SCRIPT,
            ["migration-finalize", "legacy-progress", "--decision", "delete"],
            legacy,
        )
        evidence = migrated_evidence(record)[0]
        record.write_text(record.read_text().replace(evidence, f"Different {evidence}", 1))
        (legacy / "PROGRESS.md").unlink()
        result = run_script(
            UPDATE_SCRIPT,
            ["migration-finalize", "legacy-progress", "--confirm-deleted"],
            legacy,
        )
        assert result.returncode != 0
        assert "changed after deletion approval" in result.stderr
