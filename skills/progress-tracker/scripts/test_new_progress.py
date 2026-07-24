"""Unit + integration tests for new_progress.py.

Run with: python3 -m pytest test_new_progress.py -v
(or: uv run pytest, from this directory or the repo root with rootdir set).

These tests are the primary correctness gate for the progress-tracker skill's
core script — the thing that actually writes files, unlike doc-architect's
detection logic which can only be graded by a model.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent / "new_progress.py"


def _load_module():
    """Load new_progress.py as a module without requiring a package.

    The script's PEP 723 header and hyphenated parent directory
    (skills/progress-tracker/) make a normal dotted import impractical, so
    it's loaded directly from its file path.
    """
    spec = importlib.util.spec_from_file_location("new_progress", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


np = _load_module()


def run_cli(args, cwd):
    """Invoke new_progress.py as a subprocess (exercises argparse + main())."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


# ---------------------------------------------------------------------------
# Unit tests: pure functions
# ---------------------------------------------------------------------------


class TestValidateSlug:
    def test_accepts_valid_slugs(self):
        for slug in ("subscription-refund", "a", "task-123", "abc123"):
            np.validate_slug(slug)  # must not raise / exit

    @pytest.mark.parametrize(
        "slug",
        ["Subscription-Refund", "task_123", "task 123", "-task", "TASK", ""],
    )
    def test_rejects_invalid_slugs(self, slug):
        with pytest.raises(SystemExit):
            np.validate_slug(slug)


class TestNormalizeTicket:
    def test_empty_uses_default(self):
        assert np.normalize_ticket("", default="N/A") == "N/A"
        assert np.normalize_ticket(None, default="TBD") == "TBD"

    def test_verbatim_no_normalization(self):
        # Unlike the Kdan-specific predecessor, pure digits are NOT '#'-prefixed.
        assert np.normalize_ticket("111") == "111"
        assert np.normalize_ticket("JIRA-111") == "JIRA-111"
        assert np.normalize_ticket("#111") == "#111"
        assert np.normalize_ticket("https://example.com/issues/1") == "https://example.com/issues/1"

    def test_trims_whitespace(self):
        assert np.normalize_ticket("  111  ") == "111"


class TestParseScope:
    def test_single_entry_name_only(self):
        entries = np.parse_scope("api")
        assert entries == [("api", "TBD", "TBD")]

    def test_multiple_entries(self):
        entries = np.parse_scope("api:feature/x:JIRA-1,worker")
        assert entries == [
            ("api", "feature/x", "JIRA-1"),
            ("worker", "TBD", "TBD"),
        ]

    def test_no_directory_validation(self, tmp_path, monkeypatch):
        # A scope name that does NOT exist as a directory anywhere must still
        # be accepted — this is the key de-Kdan-ification of --services.
        monkeypatch.chdir(tmp_path)
        entries = np.parse_scope("totally-made-up-service-name")
        assert entries[0][0] == "totally-made-up-service-name"

    def test_empty_scope_errors(self):
        with pytest.raises(SystemExit):
            np.parse_scope("")

    def test_empty_name_in_entry_errors(self):
        with pytest.raises(SystemExit):
            np.parse_scope(":feature/x:JIRA-1")

    def test_ticket_kept_verbatim_in_scope(self):
        entries = np.parse_scope("api::100")
        assert entries == [("api", "TBD", "100")]


class TestResolvePlan:
    def test_no_plan(self):
        assert np.resolve_plan(None) == ("N/A", None)

    def test_path_input_exists(self, tmp_path):
        plan = tmp_path / "my-plan.md"
        plan.write_text("hello")
        name, path = np.resolve_plan(str(plan))
        assert name == "my-plan.md"
        assert path == plan

    def test_path_input_missing_errors(self, tmp_path):
        with pytest.raises(SystemExit):
            np.resolve_plan(str(tmp_path / "nope.md"))

    def test_path_input_directory_errors(self, tmp_path):
        with pytest.raises(SystemExit):
            np.resolve_plan(str(tmp_path))

    def test_relative_path_input(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "plan.md").write_text("hi")
        name, path = np.resolve_plan("./plan.md")
        assert name == "plan.md"
        assert path == Path("./plan.md")

    def test_bare_filename_without_env_errors(self, monkeypatch):
        monkeypatch.delenv("PROGRESS_TRACKER_PLANS_DIR", raising=False)
        with pytest.raises(SystemExit):
            np.resolve_plan("bare-name.md")

    def test_bare_filename_resolved_via_env(self, tmp_path, monkeypatch):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "bare-name.md").write_text("hi")
        monkeypatch.setenv("PROGRESS_TRACKER_PLANS_DIR", str(plans_dir))
        name, path = np.resolve_plan("bare-name.md")
        assert name == "bare-name.md"
        assert path == plans_dir / "bare-name.md"

    def test_bare_filename_not_found_lists_candidates(self, tmp_path, monkeypatch, capsys=None):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "close-match.md").write_text("hi")
        monkeypatch.setenv("PROGRESS_TRACKER_PLANS_DIR", str(plans_dir))
        with pytest.raises(SystemExit) as exc_info:
            np.resolve_plan("close-matc.md")
        assert "close-match.md" in str(exc_info.value)


class TestRenderScopeRows:
    def test_tbd_branch_not_backticked(self):
        rows = np.render_scope_rows([("api", "TBD", "TBD")])
        assert rows == "| `api` | TBD | TBD |  |"

    def test_real_branch_backticked(self):
        rows = np.render_scope_rows([("api", "feature/x", "JIRA-1")])
        assert rows == "| `api` | `feature/x` | JIRA-1 |  |"

    def test_multiple_rows(self):
        rows = np.render_scope_rows([("api", "TBD", "TBD"), ("worker", "TBD", "TBD")])
        assert len(rows.splitlines()) == 2


class TestResolveProjectRoot:
    def test_explicit_root(self, tmp_path):
        assert np.resolve_project_root(str(tmp_path)) == tmp_path.absolute()

    def test_explicit_root_must_exist(self, tmp_path):
        with pytest.raises(SystemExit):
            np.resolve_project_root(str(tmp_path / "does-not-exist"))

    def test_git_toplevel_detected(self, tmp_path, monkeypatch):
        init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        root = np.resolve_project_root(None)
        # Resolve symlinks (e.g. /tmp -> /private/tmp on macOS) before comparing.
        assert root.resolve() == tmp_path.resolve()

    def test_falls_back_to_cwd_outside_git(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # tmp_path itself is very unlikely to be inside a git repo in CI/sandboxes,
        # but guard anyway: only assert when git genuinely reports nothing.
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=tmp_path, capture_output=True, check=False
        )
        if result.returncode != 0:
            root = np.resolve_project_root(None)
            assert root == tmp_path


class TestResolveTrackerDir:
    def test_accepts_hidden_and_nested_relative_paths(self, tmp_path):
        hidden, hidden_name = np.resolve_tracker_dir(tmp_path, ".progress")
        nested, nested_name = np.resolve_tracker_dir(tmp_path, "docs/progress/")
        assert hidden == tmp_path / ".progress"
        assert hidden_name == ".progress"
        assert nested == tmp_path / "docs" / "progress"
        assert nested_name == "docs/progress"

    @pytest.mark.parametrize("dirname", [".", "..", "../progress", "docs/../../progress"])
    def test_rejects_root_and_parent_traversal(self, tmp_path, dirname):
        with pytest.raises(SystemExit):
            np.resolve_tracker_dir(tmp_path, dirname)

    def test_rejects_absolute_path(self, tmp_path):
        with pytest.raises(SystemExit):
            np.resolve_tracker_dir(tmp_path, str(tmp_path / "progress"))

    def test_rejects_symlink_escape(self, tmp_path):
        project = tmp_path / "project"
        outside = tmp_path / "outside"
        project.mkdir()
        outside.mkdir()
        (project / "linked-progress").symlink_to(outside, target_is_directory=True)
        with pytest.raises(SystemExit):
            np.resolve_tracker_dir(project, "linked-progress")


# ---------------------------------------------------------------------------
# Integration tests: full CLI invocations against a scratch project
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path):
    init_git_repo(tmp_path)
    return tmp_path


class TestCliDryRun:
    def test_dry_run_writes_nothing(self, project):
        result = run_cli(["demo-task", "--scope", "api", "--dry-run"], cwd=project)
        assert result.returncode == 0, result.stderr
        assert "[dry-run]" in result.stdout
        assert not (project / "progress").exists()

    def test_dry_run_preview_contains_template_fields(self, project):
        result = run_cli(
            ["demo-task", "--scope", "api:feature/x:JIRA-1", "--ticket", "EPIC-1", "--dry-run"],
            cwd=project,
        )
        assert result.returncode == 0, result.stderr
        assert "Demo Task" in result.stdout
        assert "EPIC-1" in result.stdout
        assert "feature/x" in result.stdout

    def test_dry_run_index_preview_uses_real_tracker_dirname(self, project):
        # Regression: on a fresh project (tracker dir not yet scaffolded),
        # the dry-run preview must still show the real tracker dirname
        # ("progress/...") in the previewed INDEX row — not an internal
        # fallback path used only to render the template preview.
        result = run_cli(["demo-task", "--scope", "api", "--dry-run"], cwd=project)
        assert result.returncode == 0, result.stderr
        assert "`progress/" in result.stdout
        assert "`references/" not in result.stdout

    def test_dry_run_index_preview_respects_custom_dir(self, project):
        result = run_cli(
            ["demo-task", "--scope", "api", "--dir", "dev-log", "--dry-run"], cwd=project
        )
        assert result.returncode == 0, result.stderr
        assert "`dev-log/" in result.stdout
        assert "`references/" not in result.stdout


class TestCliCreate:
    def test_scaffolds_tracker_dir_on_first_use(self, project):
        result = run_cli(["demo-task", "--scope", "api"], cwd=project)
        assert result.returncode == 0, result.stderr
        tracker = project / "progress"
        assert (tracker / "README.md").exists()
        assert (tracker / "INDEX.md").exists()
        assert (tracker / "_template" / "PROGRESS.md").exists()
        assert (tracker / "_plans" / "README.md").exists()

    def test_creates_item_folder_and_file(self, project):
        result = run_cli(["demo-task", "--scope", "api"], cwd=project)
        assert result.returncode == 0, result.stderr
        item_dirs = list((project / "progress").glob("*-demo-task"))
        assert len(item_dirs) == 1
        progress_file = item_dirs[0] / "PROGRESS.md"
        assert progress_file.exists()
        content = progress_file.read_text()
        assert "Demo Task" in content
        assert "**Status:** planning" in content
        assert "{{" not in content  # no leftover placeholders

    def test_index_row_appended_with_planning_status(self, project):
        run_cli(["demo-task", "--scope", "api"], cwd=project)
        index = (project / "progress" / "INDEX.md").read_text()
        assert "| `planning` | Demo Task |" in index
        assert "`api`" in index

    def test_scope_row_expansion_multi_scope(self, project):
        run_cli(
            ["multi-task", "--scope", "api:feature/x:JIRA-1,worker:feature/y"],
            cwd=project,
        )
        item_dirs = list((project / "progress").glob("*-multi-task"))
        content = (item_dirs[0] / "PROGRESS.md").read_text()
        assert "| `api` | `feature/x` | JIRA-1 |  |" in content
        assert "| `worker` | `feature/y` | TBD |  |" in content

    def test_ticket_kept_verbatim_end_to_end(self, project):
        run_cli(["ticket-task", "--scope", "api", "--ticket", "100"], cwd=project)
        item_dirs = list((project / "progress").glob("*-ticket-task"))
        content = (item_dirs[0] / "PROGRESS.md").read_text()
        assert "**Ticket:** 100" in content  # not '#100'

    def test_refuses_to_overwrite_existing_folder(self, project):
        run_cli(["dup-task", "--scope", "api"], cwd=project)
        result = run_cli(["dup-task", "--scope", "api"], cwd=project)
        assert result.returncode != 0
        assert "already exists" in result.stderr

    def test_no_directory_validation_for_scope_name(self, project):
        # Made-up scope name must succeed — no "directory not found" error.
        result = run_cli(["ghost-task", "--scope", "nonexistent-service-xyz"], cwd=project)
        assert result.returncode == 0, result.stderr


class TestCliPlanIntegration:
    def test_plan_copied_and_linked(self, project):
        plan = project / "my-plan.md"
        plan.write_text("# The Plan\n")
        result = run_cli(["planned-task", "--scope", "api", "--plan", str(plan)], cwd=project)
        assert result.returncode == 0, result.stderr
        assert (project / "progress" / "_plans" / "my-plan.md").exists()
        item_dirs = list((project / "progress").glob("*-planned-task"))
        content = (item_dirs[0] / "PROGRESS.md").read_text()
        assert "../_plans/my-plan.md" in content

    def test_plan_snapshot_not_overwritten(self, project):
        plan = project / "my-plan.md"
        plan.write_text("# The Plan\n")
        run_cli(["task-a", "--scope", "api", "--plan", str(plan)], cwd=project)
        # A second task reusing the same plan filename must not clobber the snapshot.
        result = run_cli(["task-b", "--scope", "api", "--plan", str(plan)], cwd=project)
        assert result.returncode != 0
        assert "already exists" in result.stderr
        assert not list((project / "progress").glob("*-task-b"))
        assert "Task B" not in (project / "progress" / "INDEX.md").read_text()

    def test_broken_index_fails_before_writing_anything(self, project):
        tracker = project / "progress"
        tracker.mkdir()
        (tracker / "INDEX.md").write_text("# No item table here\n")
        plan = project / "my-plan.md"
        plan.write_text("# The Plan\n")

        result = run_cli(
            ["broken-index", "--scope", "api", "--plan", str(plan)], cwd=project
        )

        assert result.returncode != 0
        assert "table header marker" in result.stderr
        assert not list(tracker.glob("*-broken-index"))
        assert not (tracker / "_plans" / "my-plan.md").exists()
        assert not (tracker / "README.md").exists()


class TestCliCustomDirAndRoot:
    def test_custom_dir(self, project):
        result = run_cli(["custom-dir-task", "--scope", "api", "--dir", "dev-log"], cwd=project)
        assert result.returncode == 0, result.stderr
        assert (project / "dev-log").exists()
        assert not (project / "progress").exists()

    def test_nested_custom_dir(self, project):
        result = run_cli(
            ["nested-dir-task", "--scope", "api", "--dir", "docs/progress/"],
            cwd=project,
        )
        assert result.returncode == 0, result.stderr
        assert (project / "docs" / "progress").exists()
        index = (project / "docs" / "progress" / "INDEX.md").read_text()
        assert "`docs/progress/" in index

    def test_project_root_as_custom_dir_writes_nothing(self, project):
        result = run_cli(
            ["escape-task", "--scope", "api", "--dir", "."], cwd=project
        )
        assert result.returncode != 0
        assert "--dir" in result.stderr
        assert not list(project.glob("*-escape-task"))

    def test_parent_escape_writes_nothing(self, project):
        escaped_name = f"escaped-{project.name}"
        escaped = project.parent / escaped_name
        result = run_cli(
            ["escape-task", "--scope", "api", "--dir", f"../{escaped_name}"],
            cwd=project,
        )
        assert result.returncode != 0
        assert "--dir" in result.stderr
        assert not escaped.exists()

    def test_custom_root(self, tmp_path):
        # Root passed explicitly even though cwd is elsewhere.
        other_cwd = tmp_path / "elsewhere"
        other_cwd.mkdir()
        target_root = tmp_path / "target"
        target_root.mkdir()
        result = run_cli(
            ["root-task", "--scope", "api", "--root", str(target_root)], cwd=other_cwd
        )
        assert result.returncode == 0, result.stderr
        assert (target_root / "progress").exists()
        assert not (other_cwd / "progress").exists()

    def test_env_var_dir(self, project):
        env_result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "env-dir-task", "--scope", "api"],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PROGRESS_TRACKER_DIR": "custom-progress"},
        )
        assert env_result.returncode == 0, env_result.stderr
        assert (project / "custom-progress").exists()

    def test_env_var_dir_uses_same_validation(self, project):
        escaped_name = f"env-escaped-{project.name}"
        env_result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "env-escape-task", "--scope", "api"],
            cwd=project,
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "PROGRESS_TRACKER_DIR": f"../{escaped_name}",
            },
        )
        assert env_result.returncode != 0
        assert not (project.parent / escaped_name).exists()


class TestCliTitleDefaulting:
    def test_title_defaults_from_slug(self, project):
        run_cli(["my-cool-task", "--scope", "api"], cwd=project)
        item_dirs = list((project / "progress").glob("*-my-cool-task"))
        content = (item_dirs[0] / "PROGRESS.md").read_text()
        assert content.startswith("# My Cool Task")

    def test_explicit_title_used(self, project):
        run_cli(["my-task", "--scope", "api", "--title", "Custom Title Here"], cwd=project)
        item_dirs = list((project / "progress").glob("*-my-task"))
        content = (item_dirs[0] / "PROGRESS.md").read_text()
        assert content.startswith("# Custom Title Here")


class TestCliValidation:
    def test_invalid_slug_rejected(self, project):
        result = run_cli(["Invalid_Slug", "--scope", "api"], cwd=project)
        assert result.returncode != 0
        assert "slug" in result.stderr.lower()

    def test_missing_required_scope_rejected(self, project):
        result = run_cli(["my-task"], cwd=project)
        assert result.returncode != 0
