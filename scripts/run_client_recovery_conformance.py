#!/usr/bin/env python3
"""Run the shared SDK recovery scenarios through a language-specific adapter."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "client-recovery" / "scenarios.yaml"
ADAPTER_INPUT_FIELDS = ("id", "level", "name", "precondition", "faults")


class ConformanceFailure(ValueError):
    """An adapter result did not satisfy its shared scenario."""


def load_scenarios(claim: str, selected: set[str]) -> list[dict[str, Any]]:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
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
) -> None:
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
    for scenario in scenarios:
        try:
            run_scenario(scenario, args.adapter, args.timeout)
            print(f"PASS {scenario['id']}: {scenario['name']}")
        except ConformanceFailure as error:
            failures.append(str(error))
            print(f"FAIL {error}", file=sys.stderr)
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
