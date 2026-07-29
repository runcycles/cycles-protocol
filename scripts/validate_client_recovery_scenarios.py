#!/usr/bin/env python3
"""Validate the shared SDK recovery scenario catalog."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "client-recovery" / "scenarios.yaml"
ID_PATTERN = re.compile(r"^CR-(CORE|DURABLE|BOUNDARY)-\d{3}$")
LEVELS = {"core", "durable", "boundary"}
REQUIRED_FIELDS = {
    "id",
    "level",
    "name",
    "precondition",
    "faults",
    "expected_requests",
    "assertions",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def nonempty_strings(value: object, field: str, scenario_id: str) -> list[str]:
    require(isinstance(value, list), f"{scenario_id}: {field} must be a list")
    require(
        all(isinstance(item, str) and item for item in value),
        f"{scenario_id}: {field} must contain only non-empty strings",
    )
    return value


def main() -> None:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "catalog root must be a mapping")
    require(data.get("profile") == "cycles-sdk-recovery", "unexpected profile name")
    require(isinstance(data.get("version"), str), "version must be a string")

    scenarios = data.get("scenarios")
    require(isinstance(scenarios, list) and scenarios, "scenarios must be non-empty")

    seen: set[str] = set()
    for scenario in scenarios:
        require(isinstance(scenario, dict), "each scenario must be a mapping")
        require(
            set(scenario) == REQUIRED_FIELDS,
            f"{scenario.get('id', '<unknown>')}: fields must be exactly "
            f"{sorted(REQUIRED_FIELDS)}",
        )
        scenario_id = scenario["id"]
        require(
            isinstance(scenario_id, str) and ID_PATTERN.fullmatch(scenario_id),
            f"invalid scenario id: {scenario_id!r}",
        )
        require(scenario_id not in seen, f"duplicate scenario id: {scenario_id}")
        seen.add(scenario_id)

        level = scenario["level"]
        require(level in LEVELS, f"{scenario_id}: unknown level {level!r}")
        require(
            scenario_id.startswith(f"CR-{level.upper()}-"),
            f"{scenario_id}: id and level disagree",
        )
        require(
            isinstance(scenario["name"], str) and scenario["name"].strip(),
            f"{scenario_id}: name must be non-empty",
        )
        require(
            isinstance(scenario["precondition"], str)
            and scenario["precondition"].strip(),
            f"{scenario_id}: precondition must be non-empty",
        )
        faults = nonempty_strings(scenario["faults"], "faults", scenario_id)
        requests = nonempty_strings(
            scenario["expected_requests"], "expected_requests", scenario_id
        )
        assertions = nonempty_strings(
            scenario["assertions"], "assertions", scenario_id
        )
        require(
            len(requests) == len(set(requests)),
            f"{scenario_id}: duplicate expected request",
        )
        require(
            len(assertions) == len(set(assertions)),
            f"{scenario_id}: duplicate assertion",
        )

        if level == "durable":
            require(
                any("journal" in item or "record" in item for item in faults + assertions),
                f"{scenario_id}: durable scenario must exercise persisted state",
            )
        if scenario["precondition"] == "actual_unknown":
            require(
                requests == [],
                f"{scenario_id}: actual-unknown boundary cannot expect settlement",
            )

    require(
        {"core", "durable", "boundary"}
        == {scenario["level"] for scenario in scenarios},
        "catalog must cover core, durable, and boundary levels",
    )
    print(f"Validated {len(scenarios)} SDK recovery scenarios ({data['version']}).")


if __name__ == "__main__":
    main()
