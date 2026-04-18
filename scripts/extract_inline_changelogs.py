#!/usr/bin/env python3
"""
One-shot migration: extract the inline `CHANGELOG:` sub-blocks from each source
spec's `info.description` and write them to `changelogs/<spec>.md` in
Keep-a-Changelog format.

This script runs ONCE to migrate the existing ~1,300 lines of changelog content
out of the YAML spec files. After migration, new entries are added directly to
the markdown files; this script can be deleted (kept in-repo for audit).

Run: python scripts/extract_inline_changelogs.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


def load_spec_at_head(spec_filename: str) -> dict | None:
    """
    Load a spec file from git HEAD (the version before changelog extraction).
    Falls back to the working-tree file if the file isn't in HEAD.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{spec_filename}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        return yaml.safe_load(result.stdout)
    except subprocess.CalledProcessError:
        return None

REPO_ROOT = Path(__file__).resolve().parent.parent

# Source YAML -> changelog markdown filename stem (no extension).
SPECS = {
    "cycles-protocol-v0.yaml": "cycles-protocol-v0",
    "cycles-governance-admin-v0.1.25.yaml": "cycles-governance-admin",
    "cycles-action-kinds-v0.1.26.yaml": "cycles-action-kinds",
    "cycles-protocol-extensions-v0.1.26.yaml": "cycles-protocol-extensions",
    "cycles-governance-extensions-v0.1.26.yaml": "cycles-governance-extensions",
}

# Detects the START of a changelog header at a given indent. We look for a line
# whose leading-whitespace == base_indent and whose non-whitespace begins with
# `v\d+` (followed by either a digit, dot, space, paren, or arrow). Headers may
# span multiple lines (e.g., admin uses single-line `vX.Y.Z (YYYY-MM-DD):` but
# protocol uses `vX.Y.Z (revision YYYY-MM-DD — long text):` that wraps).
#
# Examples we must recognise:
#   v0.1.25.25 (2026-04-17):                                # admin format
#   v0.1.25 (revision 2026-04-16 — server-side sort ...):   # protocol single-line
#   v0.1.25 (revision 2026-04-13b — clarify admin-release   # protocol multi-line
#           discoverability):                                #   continuation
#   v0.1.25 (initial 2026-04-01, revisions 2026-04-10 ...): # alt parenthetical
#   v0.1.0 → v0.1.21:                                       # range summary
HEADER_START_RE = re.compile(r"^v(?P<version>\d+(?:\.\d+)*(?:\s*→\s*v\d+(?:\.\d+)*)?)(?P<rest>\b.*)$")
DATE_RE = re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b")
CHANGELOG_MARKER_RE = re.compile(r"^\s*CHANGELOG:\s*$")


@dataclass
class Entry:
    version: str
    date: str
    body: str  # raw indented text from the YAML, with heading stripped
    subtitle: str = ""  # parenthetical/qualifier from the original header


def split_description(description: str) -> tuple[str, list[str]]:
    """
    Split a description string on the `CHANGELOG:` marker.
    Returns (prose_before_changelog, changelog_body_lines).
    If no CHANGELOG marker is found, returns (description, []).
    """
    lines = description.splitlines()
    for i, line in enumerate(lines):
        if CHANGELOG_MARKER_RE.match(line):
            before = "\n".join(lines[:i]).rstrip() + "\n"
            changelog_lines = lines[i + 1 :]
            return before, changelog_lines
    return description, []


def _detect_base_indent(changelog_lines: list[str]) -> int:
    """Indent of the first non-blank line in the changelog block."""
    for line in changelog_lines:
        if line.strip():
            return len(line) - len(line.lstrip(" "))
    return 0


def _is_header_start(line: str, base_indent: int) -> bool:
    """A header starts with exactly `base_indent` spaces and `v\\d+`."""
    if not line.strip():
        return False
    leading = len(line) - len(line.lstrip(" "))
    if leading != base_indent:
        return False
    return bool(HEADER_START_RE.match(line.strip()))


def parse_entries(changelog_lines: list[str]) -> list[Entry]:
    """
    Parse changelog body lines into entries. Handles:
      - single-line headers (admin format)
      - multi-line headers wrapped across lines (protocol format)
      - varied parenthetical content (date, revision tag, range summary)
    """
    entries: list[Entry] = []
    base_indent = _detect_base_indent(changelog_lines)
    body_indent = base_indent + 2  # bullets sit one level deeper

    current_header_lines: list[str] = []
    current_body: list[str] = []
    in_entry = False

    def flush():
        nonlocal current_header_lines, current_body, in_entry
        if not current_header_lines:
            return
        # The first header line begins with `vX.Y.Z` (after stripping leading ws).
        first = current_header_lines[0].strip()
        m = HEADER_START_RE.match(first)
        version = m.group("version") if m else "unknown"
        # Reconstruct full header text (joined w/ spaces, trailing `:` removed).
        joined = " ".join(s.strip() for s in current_header_lines).rstrip()
        if joined.endswith(":"):
            joined = joined[:-1].rstrip()
        # Date: first YYYY-MM-DD anywhere in the joined header.
        d = DATE_RE.search(joined)
        date = d.group("date") if d else ""
        # Subtitle = anything after the version token in the joined header.
        subtitle = joined[len("v" + version):].strip()
        if subtitle.startswith("("):
            subtitle = subtitle  # keep the parenthetical
        body = "\n".join(current_body).rstrip()
        entries.append(Entry(version=version, date=date, body=body, subtitle=subtitle))
        current_header_lines = []
        current_body = []
        in_entry = False

    i = 0
    while i < len(changelog_lines):
        line = changelog_lines[i]
        if _is_header_start(line, base_indent):
            flush()
            in_entry = True
            current_header_lines = [line]
            # Continue accumulating header lines until we hit one ending with `:`
            # OR the next line is itself a body bullet at body_indent.
            while not current_header_lines[-1].rstrip().endswith(":"):
                if i + 1 >= len(changelog_lines):
                    break
                nxt = changelog_lines[i + 1]
                # Stop if next line is empty, a body bullet, or a new header.
                stripped_nxt = nxt.lstrip(" ")
                nxt_indent = len(nxt) - len(stripped_nxt)
                if not stripped_nxt:
                    break
                if stripped_nxt.startswith("- "):
                    break
                if _is_header_start(nxt, base_indent):
                    break
                if nxt_indent <= base_indent:
                    break
                current_header_lines.append(nxt)
                i += 1
            i += 1
            continue
        if in_entry:
            # Strip body indent for natural-reading markdown.
            if line.startswith(" " * body_indent):
                current_body.append(line[body_indent:])
            else:
                current_body.append(line)
        i += 1

    flush()
    return entries


def render_markdown(spec_filename: str, stem: str, entries: list[Entry]) -> str:
    """Render a Keep-a-Changelog style markdown file."""
    lines: list[str] = []
    lines.append(f"# {stem} — Changelog")
    lines.append("")
    lines.append(
        "Keep-a-Changelog format. Most recent first. Each entry corresponds to "
        f"an `info.version` bump in `{spec_filename}`."
    )
    lines.append("")
    lines.append(
        "New entries are added directly to this file. See "
        "`scripts/validate_changelogs.py` for the CI check that keeps this in "
        "sync with the spec."
    )
    lines.append("")
    for entry in entries:
        lines.append("---")
        lines.append("")
        if entry.date:
            lines.append(f"## v{entry.version} — {entry.date}")
        else:
            lines.append(f"## v{entry.version}")
        lines.append("")
        if entry.subtitle and entry.subtitle != f"({entry.date})":
            lines.append(f"_{entry.subtitle}_")
            lines.append("")
        if entry.body.strip():
            lines.append(entry.body)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    changelogs_dir = REPO_ROOT / "changelogs"
    changelogs_dir.mkdir(exist_ok=True)

    total_entries = 0
    total_lines_removed = 0

    for spec_filename, stem in SPECS.items():
        spec_path = REPO_ROOT / spec_filename
        if not spec_path.exists():
            print(f"SKIP: {spec_filename} not found", file=sys.stderr)
            continue

        # Prefer git HEAD: source YAMLs may have already been stripped of their
        # inline CHANGELOG by `strip_inline_changelog.py`. HEAD still has the
        # original prose.
        doc = load_spec_at_head(spec_filename)
        if doc is None:
            with spec_path.open(encoding="utf-8") as f:
                doc = yaml.safe_load(f)

        description = doc.get("info", {}).get("description", "")
        before, changelog_lines = split_description(description)

        if not changelog_lines:
            print(f"  {spec_filename}: no CHANGELOG: block found in HEAD, skipping")
            continue

        entries = parse_entries(changelog_lines)
        if not entries:
            print(
                f"WARN: {spec_filename} had CHANGELOG: marker but no parseable "
                "entries",
                file=sys.stderr,
            )
            continue

        md_path = changelogs_dir / f"{stem}.md"
        md_path.write_text(render_markdown(spec_filename, stem, entries), encoding="utf-8")

        original_line_count = description.count("\n")
        new_line_count = before.count("\n")
        lines_removed = original_line_count - new_line_count
        total_lines_removed += lines_removed
        total_entries += len(entries)

        print(
            f"  {spec_filename}: {len(entries)} entries -> {md_path.relative_to(REPO_ROOT)} "
            f"({lines_removed} lines removable from description)"
        )

    print(
        f"\nExtracted {total_entries} entries across {len(SPECS)} specs. "
        f"{total_lines_removed} lines of description can be removed from source YAMLs."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
