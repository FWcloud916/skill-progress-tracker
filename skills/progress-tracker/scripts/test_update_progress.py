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
