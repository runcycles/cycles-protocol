#!/usr/bin/env python3
"""Validate cycles-spec-index.yaml version pins against canonical specs.

The OpenAPI documents are authoritative. For every document in the index, this
check compares both the document-level ``version`` and its duplicate
``spec_family.current_versions`` pin with the referenced spec's
``info.version``.

Exit code 0 on success, 1 on any validation error.

Run: python scripts/validate_spec_index_versions.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO_ROOT / "cycles-spec-index.yaml"

# ``current_versions`` uses the opposite word order from the document IDs for
# base and extension specs. Keep that relationship explicit so both duplicate
# pins are checked and a newly indexed document cannot bypass CI.
CURRENT_VERSION_KEY_BY_DOCUMENT_ID = {
    "runtime_base": "base_runtime",
    "governance_base": "base_governance",
    "action_kinds": "action_kinds",
    "runtime_extension": "extension_runtime",
    "governance_extension": "extension_governance",
    "evidence_envelope": "evidence_envelope",
}


def load_yaml(path: Path) -> tuple[Any | None, str | None]:
    """Return parsed YAML and an error string, if parsing or reading fails."""
    try:
        with path.open(encoding="utf-8") as stream:
            return yaml.safe_load(stream), None
    except (OSError, yaml.YAMLError) as exc:
        return None, f"{path.relative_to(REPO_ROOT)}: cannot read YAML: {exc}"


def scalar_version(value: Any) -> str | None:
    """Normalize a scalar YAML version to text; reject absent/structured data."""
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value)


def validate() -> list[str]:
    """Return all index-version validation errors."""
    errors: list[str] = []
    index, load_error = load_yaml(INDEX_PATH)
    if load_error:
        return [load_error]
    if not isinstance(index, dict):
        return ["cycles-spec-index.yaml: top level must be a mapping"]

    spec_family = index.get("spec_family")
    if not isinstance(spec_family, dict):
        return ["cycles-spec-index.yaml: spec_family must be a mapping"]
    current_versions = spec_family.get("current_versions")
    if not isinstance(current_versions, dict):
        return [
            "cycles-spec-index.yaml: spec_family.current_versions must be a mapping"
        ]

    documents = index.get("documents")
    if not isinstance(documents, list):
        return ["cycles-spec-index.yaml: documents must be a list"]

    seen_ids: set[str] = set()
    seen_files: set[str] = set()

    for position, document in enumerate(documents, start=1):
        label = f"documents[{position}]"
        if not isinstance(document, dict):
            errors.append(f"{label}: entry must be a mapping")
            continue

        document_id = document.get("id")
        filename = document.get("file")
        if not isinstance(document_id, str) or not document_id:
            errors.append(f"{label}: id must be a non-empty string")
            continue
        label = document_id

        if document_id in seen_ids:
            errors.append(f"{label}: duplicate document id")
        seen_ids.add(document_id)

        if not isinstance(filename, str) or not filename:
            errors.append(f"{label}: file must be a non-empty string")
            continue
        if filename in seen_files:
            errors.append(f"{label}: duplicate referenced file {filename}")
        seen_files.add(filename)

        spec_path = (REPO_ROOT / filename).resolve()
        try:
            spec_path.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"{label}: file resolves outside the repository: {filename}")
            continue
        if not spec_path.is_file():
            errors.append(f"{label}: referenced spec not found: {filename}")
            continue

        spec, spec_error = load_yaml(spec_path)
        if spec_error:
            errors.append(spec_error)
            continue
        if not isinstance(spec, dict):
            errors.append(f"{label}: {filename} top level must be a mapping")
            continue

        info = spec.get("info")
        authoritative_version = scalar_version(
            info.get("version") if isinstance(info, dict) else None
        )
        if authoritative_version is None:
            errors.append(f"{label}: {filename} is missing scalar info.version")
            continue

        document_version = scalar_version(document.get("version"))
        if document_version is None:
            errors.append(f"{label}: index document is missing scalar version")
        elif document_version != authoritative_version:
            errors.append(
                f"{label}: index document version is {document_version}, but "
                f"{filename} info.version is {authoritative_version}"
            )

        current_key = CURRENT_VERSION_KEY_BY_DOCUMENT_ID.get(document_id)
        if current_key is None:
            errors.append(
                f"{label}: no current_versions key mapping; add this document to "
                "CURRENT_VERSION_KEY_BY_DOCUMENT_ID"
            )
            continue

        current_version = scalar_version(current_versions.get(current_key))
        if current_version is None:
            errors.append(
                f"{label}: spec_family.current_versions.{current_key} is missing "
                "or is not scalar"
            )
        elif current_version != authoritative_version:
            errors.append(
                f"{label}: spec_family.current_versions.{current_key} is "
                f"{current_version}, but {filename} info.version is "
                f"{authoritative_version}"
            )

    missing_documents = set(CURRENT_VERSION_KEY_BY_DOCUMENT_ID) - seen_ids
    for document_id in sorted(missing_documents):
        errors.append(
            f"version mapping references missing documents entry: {document_id}"
        )

    mapped_current_keys = set(CURRENT_VERSION_KEY_BY_DOCUMENT_ID.values())
    exempt_current_keys = {
        key
        for key in current_versions
        if key == "spec_index" or key.endswith("_semantic_base")
    }
    unvalidated_current_keys = (
        set(current_versions) - mapped_current_keys - exempt_current_keys
    )
    for current_key in sorted(unvalidated_current_keys):
        errors.append(
            f"spec_family.current_versions.{current_key} is not associated with "
            "an indexed document"
        )

    return errors


def main() -> int:
    print("Validating spec-index version pins...")
    errors = validate()
    if errors:
        for error in errors:
            print(f"  FAIL: {error}")
        print(f"\n{len(errors)} spec-index version validation error(s).")
        return 1

    print("  OK: all document and current-version pins match spec info.version")
    print("\nAll spec-index version pins are current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
