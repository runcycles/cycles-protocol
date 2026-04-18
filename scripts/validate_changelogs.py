#!/usr/bin/env python3
"""
Validate that every source spec's inline changelog pointer is in sync with its
external changelog file.

Checks:
  1. Every source spec declares `info.x-changelog.url` pointing at an existing
     file under `changelogs/`.
  2. The most recent `## vX.Y.Z` heading in that changelog matches the spec's
     `info.version`.
  3. Every changelog file has a parseable heading structure (at least one
     `## vX.Y.Z` heading).

Exit code 0 on success, 1 on any failure. Stdout lists each check pass/fail.

Run: python scripts/validate_changelogs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCE_SPECS = [
    "cycles-protocol-v0.yaml",
    "cycles-governance-admin-v0.1.25.yaml",
    "cycles-action-kinds-v0.1.26.yaml",
    "cycles-protocol-extensions-v0.1.26.yaml",
    "cycles-governance-extensions-v0.1.26.yaml",
]

VERSION_HEADING_RE = re.compile(r"^##\s+v(?P<version>[\d.]+)(?:\s|$)")


def first_version_heading(md_path: Path) -> str | None:
    for line in md_path.read_text(encoding="utf-8").splitlines():
        m = VERSION_HEADING_RE.match(line)
        if m:
            return m.group("version")
    return None


def check_spec(spec_filename: str) -> list[str]:
    """Return list of error strings (empty if all checks pass)."""
    errors: list[str] = []
    spec_path = REPO_ROOT / spec_filename
    if not spec_path.exists():
        return [f"{spec_filename}: source spec not found"]

    with spec_path.open(encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    info = doc.get("info") or {}
    version = info.get("version")
    x_changelog = info.get("x-changelog")

    if not x_changelog:
        errors.append(
            f"{spec_filename}: missing info.x-changelog — add a pointer to the "
            "external changelog (see sibling spec for example)"
        )
        return errors

    if not isinstance(x_changelog, dict) or "url" not in x_changelog:
        errors.append(
            f"{spec_filename}: info.x-changelog must be an object with a url "
            f"field, got {type(x_changelog).__name__}"
        )
        return errors

    url = x_changelog["url"]
    # Relative pointers must resolve under the repo root.
    if url.startswith("./") or url.startswith("../") or not url.startswith(("http://", "https://")):
        md_path = (REPO_ROOT / url.lstrip("./")).resolve()
        try:
            md_path.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"{spec_filename}: x-changelog.url resolves outside repo: {md_path}")
            return errors
        if not md_path.exists():
            errors.append(f"{spec_filename}: x-changelog.url points at missing file {url}")
            return errors

        latest = first_version_heading(md_path)
        if latest is None:
            errors.append(
                f"{spec_filename}: {md_path.name} has no `## vX.Y.Z` heading"
            )
            return errors

        if latest != version:
            errors.append(
                f"{spec_filename}: info.version is v{version} but "
                f"{md_path.name} latest heading is v{latest}. Either bump the "
                "changelog or the spec version."
            )
    else:
        # Absolute URL — we can't check it from CI reliably. Accept and warn.
        print(f"  INFO: {spec_filename} uses absolute x-changelog URL {url} "
              "(skipping file existence + version sync check)")

    return errors


def main() -> int:
    all_errors: list[str] = []
    print("Validating changelog pointers...")
    for spec in SOURCE_SPECS:
        errors = check_spec(spec)
        if errors:
            for e in errors:
                print(f"  FAIL: {e}")
            all_errors.extend(errors)
        else:
            print(f"  OK:   {spec}")

    if all_errors:
        print(f"\n{len(all_errors)} changelog validation error(s).")
        return 1

    print("\nAll changelog pointers valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
