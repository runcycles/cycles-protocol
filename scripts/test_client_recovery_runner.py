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

    def test_runner_writes_structured_evidence_report(self) -> None:
        adapter_source = """
import json
import sys
scenario = json.load(sys.stdin)
json.dump({
    "scenario_id": scenario["id"],
    "passed": True,
    "native_tests": [f"native::{scenario['id']}"],
}, sys.stdout)
"""
        with tempfile.TemporaryDirectory() as directory:
            adapter = Path(directory) / "adapter.py"
            report = Path(directory) / "reports" / "recovery.json"
            adapter.write_text(adapter_source, encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(runner.__file__)),
                    "--claim",
                    "core",
                    "--report-json",
                    str(report),
                    "--implementation",
                    "example/sdk",
                    "--implementation-version",
                    "1.2.3",
                    "--implementation-commit",
                    "deadbeef",
                    "--evidence-url",
                    "https://example.test/actions/runs/42",
                    "--adapter",
                    sys.executable,
                    str(adapter),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            evidence = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(evidence["schema_version"], "1.0")
        self.assertEqual(evidence["profile"]["version"], "0.3")
        self.assertEqual(len(evidence["profile"]["catalog_sha256"]), 64)
        self.assertEqual(evidence["claim"], "core")
        self.assertEqual(evidence["implementation"], {
            "id": "example/sdk",
            "commit": "deadbeef",
            "version": "1.2.3",
        })
        self.assertEqual(
            evidence["evidence_url"],
            "https://example.test/actions/runs/42",
        )
        self.assertEqual(evidence["summary"]["failed"], 0)
        self.assertEqual(
            evidence["summary"]["passed"],
            evidence["summary"]["total"],
        )
        self.assertTrue(all(
            scenario["native_tests"] == [f"native::{scenario['id']}"]
            for scenario in evidence["scenarios"]
        ))

    def test_runner_preserves_failed_scenario_in_report(self) -> None:
        adapter_source = """
import json
import sys
scenario = json.load(sys.stdin)
json.dump({
    "scenario_id": scenario["id"],
    "passed": False,
    "native_tests": ["native::failed"],
    "diagnostic": "injected failure",
}, sys.stdout)
"""
        with tempfile.TemporaryDirectory() as directory:
            adapter = Path(directory) / "adapter.py"
            report = Path(directory) / "recovery.json"
            adapter.write_text(adapter_source, encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(runner.__file__)),
                    "--claim",
                    "core",
                    "--scenario",
                    "CR-CORE-001",
                    "--report-json",
                    str(report),
                    "--adapter",
                    sys.executable,
                    str(adapter),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            evidence = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(evidence["summary"], {
            "total": 1,
            "passed": 0,
            "failed": 1,
        })
        self.assertFalse(evidence["scenarios"][0]["passed"])
        self.assertIn(
            "injected failure",
            evidence["scenarios"][0]["diagnostic"],
        )

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
