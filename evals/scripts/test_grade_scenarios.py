#!/usr/bin/env python3
"""Free regression tests for grade_scenarios.py's grading logic.

These run against synthetic file trees (no live new_progress.py invocation,
no model call) — they protect the grader itself from false-greening, the
same discipline doc-architect's test_grade.py applies to its detection
grader. Run with: python3 test_grade_scenarios.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from grade_scenarios import grade  # noqa: E402


class GradeScenariosTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_files_exist_passes_when_present(self):
        (self.repo / "progress").mkdir()
        (self.repo / "progress" / "INDEX.md").write_text("hi")
        failures = grade(self.repo, {"files_exist": ["progress/INDEX.md"]})
        self.assertEqual(failures, [])

    def test_files_exist_fails_when_missing(self):
        failures = grade(self.repo, {"files_exist": ["progress/INDEX.md"]})
        self.assertEqual(len(failures), 1)
        self.assertIn("progress/INDEX.md", failures[0])

    def test_files_exist_glob_matches_dated_folder(self):
        item = self.repo / "progress" / "2026-01-01-my-task"
        item.mkdir(parents=True)
        (item / "PROGRESS.md").write_text("x")
        failures = grade(self.repo, {"files_exist": ["progress/*-my-task/PROGRESS.md"]})
        self.assertEqual(failures, [])

    def test_files_absent_fails_when_present(self):
        (self.repo / "progress").mkdir()
        failures = grade(self.repo, {"files_absent": ["progress"]})
        self.assertEqual(len(failures), 1)

    def test_files_absent_passes_when_missing(self):
        failures = grade(self.repo, {"files_absent": ["progress"]})
        self.assertEqual(failures, [])

    def test_content_contains_passes(self):
        (self.repo / "INDEX.md").write_text("| `planning` | Task |")
        failures = grade(
            self.repo, {"content_contains": [{"glob": "INDEX.md", "text": "`planning`"}]}
        )
        self.assertEqual(failures, [])

    def test_content_contains_fails_when_text_absent(self):
        (self.repo / "INDEX.md").write_text("| `planning` | Task |")
        failures = grade(
            self.repo, {"content_contains": [{"glob": "INDEX.md", "text": "`done`"}]}
        )
        self.assertEqual(len(failures), 1)

    def test_content_contains_fails_when_glob_matches_nothing(self):
        failures = grade(
            self.repo, {"content_contains": [{"glob": "does-not-exist.md", "text": "x"}]}
        )
        self.assertEqual(len(failures), 1)

    def test_content_not_contains_catches_leftover_placeholder(self):
        (self.repo / "PROGRESS.md").write_text("# {{TITLE}}\n")
        failures = grade(
            self.repo, {"content_not_contains": [{"glob": "PROGRESS.md", "text": "{{"}]}
        )
        self.assertEqual(len(failures), 1)

    def test_content_not_contains_passes_when_absent(self):
        (self.repo / "PROGRESS.md").write_text("# Real Title\n")
        failures = grade(
            self.repo, {"content_not_contains": [{"glob": "PROGRESS.md", "text": "{{"}]}
        )
        self.assertEqual(failures, [])

    def test_content_count_exact_match_passes(self):
        (self.repo / "INDEX.md").write_text("Dup Task\n")
        failures = grade(
            self.repo, {"content_count": [{"glob": "INDEX.md", "text": "Dup Task", "count": 1}]}
        )
        self.assertEqual(failures, [])

    def test_content_count_catches_duplicate_rows(self):
        (self.repo / "INDEX.md").write_text("Dup Task\nDup Task\n")
        failures = grade(
            self.repo, {"content_count": [{"glob": "INDEX.md", "text": "Dup Task", "count": 1}]}
        )
        self.assertEqual(len(failures), 1)

    def test_unknown_check_type_flagged(self):
        failures = grade(self.repo, {"totally_made_up_check": []})
        self.assertEqual(len(failures), 1)
        self.assertIn("unknown check type", failures[0])

    def test_multiple_check_types_combined(self):
        (self.repo / "progress").mkdir()
        (self.repo / "progress" / "INDEX.md").write_text("| `planning` | Task |")
        failures = grade(
            self.repo,
            {
                "files_exist": ["progress/INDEX.md"],
                "files_absent": ["dev-log"],
                "content_contains": [{"glob": "progress/INDEX.md", "text": "`planning`"}],
            },
        )
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
