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
    def test_runner_executes_each_core_scenario_in_a_fresh_adapter(self) -> None:
        adapter_source = """
import json
import sys
scenario = json.load(sys.stdin)
json.dump({
    "scenario_id": scenario["id"],
    "passed": True,
    "observed_requests": scenario["expected_requests"],
    "assertions": scenario["assertions"],
}, sys.stdout)
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
        expected = len(runner.load_scenarios("core", set()))
        self.assertIn(f"Passed {expected} core recovery scenarios.", completed.stdout)


if __name__ == "__main__":
    unittest.main()
