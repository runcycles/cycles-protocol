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

    def test_accepts_exact_choreography_and_required_observations(self) -> None:
        runner.validate_result(
            self.scenario,
            {
                "scenario_id": "CR-CORE-999",
                "passed": True,
                "observed_requests": ["commit", "commit_same_key"],
                "assertions": [
                    "settlement_occurs_at_most_once",
                    "adapter_specific_observation",
                ],
            },
        )

    def test_rejects_request_choreography_drift(self) -> None:
        with self.assertRaisesRegex(runner.ConformanceFailure, "choreography"):
            runner.validate_result(
                self.scenario,
                {
                    "scenario_id": "CR-CORE-999",
                    "passed": True,
                    "observed_requests": ["commit", "commit_new_key"],
                    "assertions": ["settlement_occurs_at_most_once"],
                },
            )

    def test_rejects_missing_observations(self) -> None:
        with self.assertRaisesRegex(runner.ConformanceFailure, "missing required"):
            runner.validate_result(
                self.scenario,
                {
                    "scenario_id": "CR-CORE-999",
                    "passed": True,
                    "observed_requests": ["commit", "commit_same_key"],
                    "assertions": [],
                },
            )


class ProcessAdapterTests(unittest.TestCase):
    def test_runner_hides_oracle_and_includes_boundary_scenarios(self) -> None:
        scenarios = runner.load_scenarios("core", set())
        results = {
            scenario["id"]: {
                "observed_requests": scenario["expected_requests"],
                "assertions": scenario["assertions"],
            }
            for scenario in scenarios
        }
        adapter_source = f"""
import json
import sys
scenario = json.load(sys.stdin)
assert "expected_requests" not in scenario
assert "assertions" not in scenario
results = {results!r}
observation = results[scenario["id"]]
json.dump({{
    "scenario_id": scenario["id"],
    "passed": True,
    "observed_requests": observation["observed_requests"],
    "assertions": observation["assertions"],
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
