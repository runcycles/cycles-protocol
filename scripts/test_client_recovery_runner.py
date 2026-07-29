#!/usr/bin/env python3
"""Self-tests for the language-neutral SDK recovery adapter runner."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import run_client_recovery_conformance as runner


class ResultValidationTests(unittest.TestCase):
    scenario = {
        "id": "CR-CORE-999",
        "expected_requests": ["commit", "commit_same_key"],
        "assertions": ["settlement_occurs_at_most_once"],
    }

    def test_accepts_concrete_native_test_evidence(self) -> None:
        runner.validate_result(
            self.scenario,
            {
                "scenario_id": "CR-CORE-999",
                "passed": True,
                "native_tests": [
                    "tests/recovery.test.ts > lost response reuses original key"
                ],
            },
        )

    def test_rejects_missing_native_test_evidence(self) -> None:
        with self.assertRaisesRegex(runner.ConformanceFailure, "native_tests"):
            runner.validate_result(
                self.scenario,
                {
                    "scenario_id": "CR-CORE-999",
                    "passed": True,
                    "native_tests": [],
                },
            )

    def test_rejects_duplicate_native_test_evidence(self) -> None:
        with self.assertRaisesRegex(runner.ConformanceFailure, "duplicates"):
            runner.validate_result(
                self.scenario,
                {
                    "scenario_id": "CR-CORE-999",
                    "passed": True,
                    "native_tests": ["test_one", "test_one"],
                },
            )


class ProcessAdapterTests(unittest.TestCase):
    def test_runner_hides_oracle_and_includes_boundary_scenarios(self) -> None:
        scenarios = runner.load_scenarios("core", set())
        adapter_source = f"""
import json
import sys
scenario = json.load(sys.stdin)
assert "expected_requests" not in scenario
assert "assertions" not in scenario
json.dump({{
    "scenario_id": scenario["id"],
    "passed": True,
    "native_tests": [f"native::{{scenario['id']}}"],
}}, sys.stdout)
"""
        with tempfile.TemporaryDirectory() as directory:
            adapter = Path(directory) / "adapter.py"
            adapter.write_text(adapter_source, encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(runner.__file__)),
                    "--claim",
                    "core",
                    "--adapter",
                    sys.executable,
                    str(adapter),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        expected = len(scenarios)
        self.assertIn(f"Passed {expected} core recovery scenarios.", completed.stdout)
        self.assertTrue(any(scenario["level"] == "boundary" for scenario in scenarios))

    def test_unknown_selected_scenario_is_reported_without_traceback(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(runner.__file__)),
                "--claim",
                "core",
                "--scenario",
                "CR-DURABLE-001",
                "--adapter",
                sys.executable,
                "-c",
                "raise SystemExit(0)",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("outside the core claim", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
