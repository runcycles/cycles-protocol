#!/usr/bin/env python3
"""
One-shot migration companion to `extract_inline_changelogs.py`.

For each source YAML spec:
  1. Locate the `CHANGELOG:` line inside `info.description` (a block scalar).
  2. Delete from that line to the end of the description block.
  3. Insert a one-line pointer to the external changelog above the removed block.
  4. Insert an `x-changelog` key at the `info:` level, pointing at the external
     markdown file.

Operates on the raw YAML text so that existing formatting (key order, comments,
block-scalar style) is preserved — a full `yaml.safe_load` + `yaml.dump` round
trip would re-serialize the whole file.

Run ONCE: `python scripts/strip_inline_changelog.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SPECS = {
    "cycles-protocol-v0.yaml": "cycles-protocol-v0",
    "cycles-governance-admin-v0.1.25.yaml": "cycles-governance-admin",
    "cycles-action-kinds-v0.1.26.yaml": "cycles-action-kinds",
    "cycles-protocol-extensions-v0.1.26.yaml": "cycles-protocol-extensions",
    "cycles-governance-extensions-v0.1.26.yaml": "cycles-governance-extensions",
}

CHANGELOG_LINE_RE = re.compile(r"^(?P<indent>\s+)CHANGELOG:\s*$")


def strip_spec(spec_path: Path, changelog_stem: str) -> tuple[int, int]:
    """
    Returns (removed_lines, info_line_index) for reporting.
    Edits the file in place.
    """
    lines = spec_path.read_text(encoding="utf-8").splitlines(keepends=True)

    # Find the `CHANGELOG:` marker line inside info.description.
    changelog_idx: int | None = None
    changelog_indent: int | None = None
    for i, line in enumerate(lines):
        m = CHANGELOG_LINE_RE.match(line)
        if m:
            changelog_idx = i
            changelog_indent = len(m.group("indent"))
            break

    if changelog_idx is None:
        print(f"  {spec_path.name}: no CHANGELOG: marker, skipping")
        return 0, -1

    # description is a block scalar under info.description. The block ends at the
    # first subsequent line whose indent is less than `changelog_indent` (typically
    # indent 0 — a top-level key like `servers:` — or the description's own
    # "|-" indent, which in practice equals changelog_indent - 2).
    end_idx = len(lines)
    for j in range(changelog_idx + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue  # blank lines don't terminate a block scalar
        # Count leading spaces.
        stripped_len = len(line) - len(line.lstrip(" "))
        if stripped_len < changelog_indent:
            end_idx = j
            break

    # Find the `info:` line and the `description: |-` line so we know where to
    # insert `x-changelog:` (as a sibling of description, indent = 2 if info is
    # at indent 0). We place x-changelog right before the `description:` key to
    # keep the pointer visible at the top of info.
    info_idx: int | None = None
    description_idx: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^info:\s*$", line):
            info_idx = i
        if info_idx is not None and re.match(r"^\s{2}description:\s*\|", line):
            description_idx = i
            break

    if info_idx is None or description_idx is None:
        raise RuntimeError(
            f"{spec_path.name}: couldn't locate info:/description: structure"
        )

    # The CHANGELOG: block used to live inside the description block. We just
    # delete it — discoverability is provided by the `x-changelog` vendor
    # extension added below (a sibling of `description` under `info`).
    pointer_block: list[str] = []

    # Build the x-changelog YAML block, indent 2 (sibling of description).
    x_changelog_block = [
        "  x-changelog:\n",
        f"    url: ./changelogs/{changelog_stem}.md\n",
        "    format: keep-a-changelog\n",
    ]

    # Splice: delete lines [changelog_idx:end_idx], insert pointer_block at changelog_idx.
    removed_count = end_idx - changelog_idx
    new_lines = lines[:changelog_idx] + pointer_block + lines[end_idx:]

    # Insert x-changelog_block right before the `description:` key.
    # description_idx in `lines` indexes the original array; after the earlier
    # splice, the description key is still at the same index IF description_idx
    # < changelog_idx (which it is — description comes before its body). So
    # description_idx is still valid in new_lines.
    new_lines = (
        new_lines[:description_idx]
        + x_changelog_block
        + new_lines[description_idx:]
    )

    spec_path.write_text("".join(new_lines), encoding="utf-8")
    return removed_count, info_idx


def main() -> int:
    total_removed = 0
    for spec_filename, stem in SPECS.items():
        spec_path = REPO_ROOT / spec_filename
        if not spec_path.exists():
            print(f"SKIP: {spec_filename} not found", file=sys.stderr)
            continue

        removed, _ = strip_spec(spec_path, stem)
        if removed:
            print(f"  {spec_filename}: removed {removed} lines, added x-changelog")
            total_removed += removed
        else:
            print(f"  {spec_filename}: no change")

    print(f"\nRemoved {total_removed} total lines across {len(SPECS)} specs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
