#!/usr/bin/env python3
"""Run the shared SDK recovery scenarios through a language-specific adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "client-recovery" / "scenarios.yaml"
ADAPTER_INPUT_FIELDS = ("id", "level", "name", "precondition", "faults")
REPORT_SCHEMA_VERSION = "1.0"
REPORT_SCHEMA_URL = (
    "https://raw.githubusercontent.com/runcycles/cycles-protocol/main/"
    "client-recovery/report.schema.json"
)


class ConformanceFailure(ValueError):
    """An adapter result did not satisfy its shared scenario."""


def load_catalog() -> dict[str, Any]:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConformanceFailure("recovery scenario catalog must be an object")
    return data


def load_scenarios(claim: str, selected: set[str]) -> list[dict[str, Any]]:
    data = load_catalog()
    levels = (
        {"core", "boundary"}
        if claim == "core"
        else {"core", "durable", "boundary"}
    )
    scenarios = [
        scenario
        for scenario in data["scenarios"]
        if scenario["level"] in levels
        and (not selected or scenario["id"] in selected)
    ]
    missing = selected - {scenario["id"] for scenario in scenarios}
    if missing:
        raise ConformanceFailure(
            f"selected scenarios are outside the {claim} claim or unknown: "
            f"{', '.join(sorted(missing))}"
        )
    return scenarios


def validate_result(scenario: dict[str, Any], result: object) -> None:
    scenario_id = scenario["id"]
    if not isinstance(result, dict):
        raise ConformanceFailure(f"{scenario_id}: adapter result must be an object")
    if result.get("scenario_id") != scenario_id:
        raise ConformanceFailure(f"{scenario_id}: adapter returned the wrong scenario_id")
    if result.get("passed") is not True:
        diagnostic = result.get("diagnostic", "adapter reported failure")
        raise ConformanceFailure(f"{scenario_id}: {diagnostic}")

    native_tests = result.get("native_tests")
    if not isinstance(native_tests, list) or not native_tests or not all(
        isinstance(test, str) and test.strip() for test in native_tests
    ):
        raise ConformanceFailure(
            f"{scenario_id}: native_tests must be a non-empty list of test identifiers"
        )
    if len(native_tests) != len(set(native_tests)):
        raise ConformanceFailure(
            f"{scenario_id}: native_tests must not contain duplicates"
        )


def run_scenario(
    scenario: dict[str, Any], adapter: list[str], timeout_seconds: float
) -> dict[str, Any]:
    scenario_id = scenario["id"]
    adapter_input = {field: scenario[field] for field in ADAPTER_INPUT_FIELDS}
    try:
        completed = subprocess.run(
            [*adapter, scenario_id],
            input=json.dumps(adapter_input),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ConformanceFailure(
            f"{scenario_id}: adapter exceeded {timeout_seconds:g}s"
        ) from error
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip()
        raise ConformanceFailure(
            f"{scenario_id}: adapter exited {completed.returncode}: {diagnostic}"
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ConformanceFailure(
            f"{scenario_id}: adapter stdout must be one JSON result; "
            "send diagnostic logs to stderr"
        ) from error
    validate_result(scenario, result)
    return result


def command_output(command: list[str], cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def github_run_url() -> str | None:
    server = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repository and run_id:
        return f"{server}/{repository}/actions/runs/{run_id}"
    return None


def build_report(
    args: argparse.Namespace,
    scenarios: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    catalog = load_catalog()
    implementation_commit = (
        args.implementation_commit
        or os.environ.get("GITHUB_SHA")
        or command_output(["git", "rev-parse", "HEAD"], Path.cwd())
        or "unknown"
    )
    profile_commit = (
        command_output(["git", "rev-parse", "HEAD"], ROOT)
        or "unknown"
    )
    implementation = {
        "id": (
            args.implementation
            or os.environ.get("GITHUB_REPOSITORY")
            or Path.cwd().name
        ),
        "commit": implementation_commit,
    }
    if args.implementation_version:
        implementation["version"] = args.implementation_version

    scenario_reports = []
    result_by_id = {result["scenario_id"]: result for result in results}
    for scenario in scenarios:
        result = result_by_id[scenario["id"]]
        entry = {
            "id": scenario["id"],
            "level": scenario["level"],
            "name": scenario["name"],
            "passed": result["passed"],
            "native_tests": result.get("native_tests", []),
        }
        if diagnostic := result.get("diagnostic"):
            entry["diagnostic"] = diagnostic
        scenario_reports.append(entry)

    passed = sum(1 for result in scenario_reports if result["passed"])
    report = {
        "$schema": REPORT_SCHEMA_URL,
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "profile": {
            "name": catalog["profile"],
            "version": str(catalog["version"]),
            "commit": profile_commit,
            "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        },
        "claim": args.claim,
        "implementation": implementation,
        "summary": {
            "total": len(scenario_reports),
            "passed": passed,
            "failed": len(scenario_reports) - passed,
        },
        "scenarios": scenario_reports,
    }
    evidence_url = args.evidence_url or github_run_url()
    if evidence_url:
        report["evidence_url"] = evidence_url
    return report


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", choices=("core", "durable"), required=True)
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="run only this scenario ID (repeatable)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="per-scenario adapter timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--adapter",
        nargs=argparse.REMAINDER,
        required=True,
        help="adapter command; the runner appends the scenario ID",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="atomically write a machine-readable conformance evidence report",
    )
    parser.add_argument(
        "--implementation",
        help="implementation identifier (defaults to GITHUB_REPOSITORY or cwd)",
    )
    parser.add_argument(
        "--implementation-version",
        help="optional implementation release version for the evidence report",
    )
    parser.add_argument(
        "--implementation-commit",
        help="implementation commit (defaults to GITHUB_SHA or cwd HEAD)",
    )
    parser.add_argument(
        "--evidence-url",
        help="stable URL for the CI run or other supporting evidence",
    )
    args = parser.parse_args()
    if not args.adapter:
        parser.error("--adapter requires a command")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        scenarios = load_scenarios(args.claim, set(args.scenario))
    except ConformanceFailure as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        try:
            result = run_scenario(scenario, args.adapter, args.timeout)
            results.append(result)
            print(f"PASS {scenario['id']}: {scenario['name']}")
        except ConformanceFailure as error:
            failures.append(str(error))
            results.append({
                "scenario_id": scenario["id"],
                "passed": False,
                "native_tests": [],
                "diagnostic": str(error),
            })
            print(f"FAIL {error}", file=sys.stderr)
    if args.report_json:
        try:
            write_report(
                args.report_json,
                build_report(args, scenarios, results),
            )
        except (OSError, TypeError, ValueError) as error:
            failures.append(f"could not write evidence report: {error}")
            print(f"FAIL could not write evidence report: {error}", file=sys.stderr)
    if failures:
        print(
            f"{len(failures)} of {len(scenarios)} recovery scenarios failed.",
            file=sys.stderr,
        )
        return 1
    print(f"Passed {len(scenarios)} {args.claim} recovery scenarios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
