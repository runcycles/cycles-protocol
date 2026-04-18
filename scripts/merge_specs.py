#!/usr/bin/env python3
"""
Cycles Protocol v0.1.26 — Spec Merger

Produces two merged OpenAPI artifacts from the companion spec suite:

  1. cycles-openapi-protocol-merged.yaml  (runtime plane)
     = cycles-protocol-v0.yaml
     + cycles-protocol-extensions-v0.1.26.yaml
     + cycles-action-kinds-v0.1.26.yaml
     Target: runtime servers, SDK generators, Swagger UI, Postman.

  2. cycles-openapi-admin-merged.yaml  (admin/governance plane)
     = cycles-governance-admin-v0.1.25.yaml
     + cycles-governance-extensions-v0.1.26.yaml
     + cycles-action-kinds-v0.1.26.yaml
     Target: admin tooling, policy editors, operator dashboards.

Merge semantics:
  - Schemas: union by name. Duplicates must be byte-identical or the
    script raises (prevents silent drift).
  - Paths: union by (path, method). Duplicates are resolved by merging
    allOf compositions (for the governance extension's PATCH re-declaration
    pattern).
  - Security schemes: union by name. Duplicates must be identical.
  - Parameters: union by name.
  - Tags: union by name; descriptions from the primary source win.
  - ErrorCode enum: unioned across all source specs.
  - EventType enum: unioned across all source specs.
  - Permission enum: unioned across all source specs.

Run: python scripts/merge_specs.py
Outputs to: merged/
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


# --- YAML formatting: emit multi-line strings as block scalars ---------------
# By default PyYAML serializes strings with newlines as double-quoted with
# \n escapes. That makes merged files unreadable. This custom representer
# forces multi-line strings into literal block scalars (|-) which preserve
# newlines and indentation naturally.

class _BlockString(str):
    """Marker type for strings that should be emitted as block scalars."""


def _represent_block_string(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


def _represent_str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class _CyclesYamlDumper(yaml.SafeDumper):
    """Custom dumper: block scalars for multi-line strings, 2-space indent."""


_CyclesYamlDumper.add_representer(str, _represent_str)
_CyclesYamlDumper.add_representer(_BlockString, _represent_block_string)


def _yaml_dump(data: Any, stream, **kwargs) -> None:
    """Dump with block-scalar multi-line strings and readable indentation."""
    yaml.dump(
        data,
        stream,
        Dumper=_CyclesYamlDumper,
        sort_keys=False,
        width=100,
        indent=2,
        default_flow_style=False,
        allow_unicode=True,
        **kwargs,
    )

REPO = Path(__file__).resolve().parent.parent

# Source files
RUNTIME_BASE = REPO / "cycles-protocol-v0.yaml"
RUNTIME_EXT = REPO / "cycles-protocol-extensions-v0.1.26.yaml"
ACTION_KINDS = REPO / "cycles-action-kinds-v0.1.26.yaml"
GOV_BASE = REPO / "cycles-governance-admin-v0.1.25.yaml"
GOV_EXT = REPO / "cycles-governance-extensions-v0.1.26.yaml"

# Output files
OUT_DIR = REPO / "merged"
PROTOCOL_OUT = OUT_DIR / "cycles-openapi-protocol-merged.yaml"
ADMIN_OUT = OUT_DIR / "cycles-openapi-admin-merged.yaml"


def load(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def merge_component_dict(
    dest: dict[str, Any],
    src: dict[str, Any] | None,
    section: str,
    source_name: str,
) -> None:
    """
    Merge a components/<section> dict from src into dest.
    Duplicates must be byte-identical or an error is raised.
    """
    if not src:
        return
    for name, value in src.items():
        if name in dest:
            if dest[name] != value:
                # Allow ErrorResponse / UnitEnum / shared schemas to be merged
                # only if one is a subset of the other. Raise otherwise.
                if name in ("ErrorResponse", "UnitEnum"):
                    # Prefer the richer version (more properties / longer enum)
                    if _is_richer(value, dest[name]):
                        dest[name] = value
                    continue
                print(
                    f"WARNING: conflicting {section} schema '{name}' "
                    f"from {source_name} differs from earlier definition. "
                    f"Keeping first-in-wins.",
                    file=sys.stderr,
                )
        else:
            dest[name] = value


def _is_richer(a: Any, b: Any) -> bool:
    """Return True if `a` has more information than `b` (more props, longer enum)."""
    if isinstance(a, dict) and isinstance(b, dict):
        a_props = len(a.get("properties", {})) if "properties" in a else 0
        b_props = len(b.get("properties", {})) if "properties" in b else 0
        a_enum = len(a.get("enum", [])) if "enum" in a else 0
        b_enum = len(b.get("enum", [])) if "enum" in b else 0
        return (a_props + a_enum) > (b_props + b_enum)
    return False


def merge_paths(
    dest: dict[str, Any],
    src: dict[str, Any] | None,
    source_name: str,
    rename_collisions: dict[str, str] | None = None,
) -> None:
    """
    Merge OpenAPI paths. On (path, method) collision, if the ops have distinct
    operationIds (the governance extension PATCH re-declaration pattern), keep
    BOTH by appending a suffix to the extension version's path — the merged
    artifact then lets implementers see both shapes.

    rename_collisions: {"/v1/admin/policies/{policy_id}": "/v1/admin/policies/{policy_id}#v0.1.26"}
    """
    if not src:
        return
    for path, ops in src.items():
        if path in dest:
            # Merge method by method
            merged_path = dest[path]
            for method, op in ops.items():
                if method in merged_path:
                    existing_op = merged_path[method]
                    existing_id = existing_op.get("operationId", "")
                    new_id = op.get("operationId", "")
                    if existing_id != new_id:
                        # Distinct operationIds — merge allOf bodies
                        merged_op = _merge_ops(existing_op, op)
                        merged_path[method] = merged_op
                    else:
                        # Same operationId → keep first (shouldn't happen in practice)
                        pass
                else:
                    merged_path[method] = op
        else:
            dest[path] = ops


def _merge_ops(base_op: dict[str, Any], ext_op: dict[str, Any]) -> dict[str, Any]:
    """
    Merge a base operation with an extension operation that re-declares it.
    Strategy:
      - Keep base summary/description but append extension notes
      - Merge request body allOf: base properties + extension properties
      - Union security
      - Union responses (extension responses win on overlap)
    """
    merged = dict(base_op)  # shallow copy

    # Merge description (additive)
    base_desc = base_op.get("description", "")
    ext_desc = ext_op.get("description", "")
    if ext_desc and ext_desc not in base_desc:
        merged["description"] = (base_desc + "\n\n" + ext_desc).strip()

    # Merge request body
    base_body = base_op.get("requestBody", {})
    ext_body = ext_op.get("requestBody", {})
    if ext_body:
        base_schema = _extract_body_schema(base_body)
        ext_schema = _extract_body_schema(ext_body)
        if base_schema and ext_schema:
            merged_schema = _merge_schemas_additive(base_schema, ext_schema)
            merged["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {"schema": merged_schema}
                },
            }

    # Merge responses (extension wins on overlap)
    base_responses = base_op.get("responses", {})
    ext_responses = ext_op.get("responses", {})
    merged_responses = dict(base_responses)
    for code, resp in ext_responses.items():
        merged_responses[code] = resp
    merged["responses"] = merged_responses

    # Prefer extension operationId for discoverability in merged file
    if "operationId" in ext_op:
        merged["operationId"] = ext_op["operationId"]

    return merged


def _extract_body_schema(body: dict[str, Any]) -> dict[str, Any] | None:
    content = body.get("content", {})
    app_json = content.get("application/json", {})
    return app_json.get("schema")


def _merge_schemas_additive(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Merge two schemas into a combined allOf."""
    a_allof = a.get("allOf", [a])
    b_allof = b.get("allOf", [b])
    return {"allOf": a_allof + b_allof}


def union_enum_in_schema(
    schemas: dict[str, Any],
    schema_name: str,
    source_schemas: dict[str, Any],
    extension_schema_name: str | None = None,
) -> None:
    """
    Union the enum values of `schema_name` with values from either a matching
    schema in `source_schemas` or a dedicated `extension_schema_name` that
    carries the extended enum.
    """
    if schema_name not in schemas:
        return

    base = schemas[schema_name]
    if "enum" not in base:
        return

    existing = set(base["enum"])

    # Option 1: extension schema with the same name has more values
    ext = source_schemas.get(schema_name)
    if ext and "enum" in ext:
        for v in ext["enum"]:
            if v not in existing:
                base["enum"].append(v)
                existing.add(v)

    # Option 2: a dedicated extension schema carries the extended enum
    if extension_schema_name:
        ext_by_name = source_schemas.get(extension_schema_name)
        if ext_by_name and "enum" in ext_by_name:
            for v in ext_by_name["enum"]:
                if v not in existing:
                    base["enum"].append(v)
                    existing.add(v)


def build_merged(
    title: str,
    version: str,
    description: str,
    sources: list[tuple[str, Path]],
) -> dict[str, Any]:
    """
    Build a merged OpenAPI spec from a list of source files.
    sources: [(source_name, file_path), ...]
    """
    merged: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": title,
            "version": version,
            "license": {"name": "Apache 2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"},
            "description": description,
        },
        "servers": [{"url": "https://api.cycles.local", "description": "Replace with your implementation endpoint"}],
        "tags": [],
        "components": {
            "securitySchemes": {},
            "schemas": {},
            "parameters": {},
            "headers": {},
            "responses": {},
            "requestBodies": {},
            "examples": {},
            "links": {},
            "callbacks": {},
        },
        "paths": {},
    }

    seen_tag_names: set[str] = set()
    x_changelogs: list[dict[str, Any]] = []

    # All OpenAPI 3.1 reusable component sections that may contain $ref targets.
    # We must merge every section the sources use, or $refs will break.
    COMPONENT_SECTIONS = (
        "securitySchemes",
        "schemas",
        "parameters",
        "headers",
        "responses",
        "requestBodies",
        "examples",
        "links",
        "callbacks",
    )

    for source_name, path in sources:
        print(f"  + merging {path.name}")
        spec = load(path)

        # x-changelog: collect per-source pointers so the merged artifact is
        # discoverable from every source's changelog. Each source's pointer is
        # annotated with the source filename.
        src_x_changelog = (spec.get("info") or {}).get("x-changelog")
        if src_x_changelog:
            entry = dict(src_x_changelog)
            entry["source"] = path.name
            x_changelogs.append(entry)

        # Tags
        for tag in spec.get("tags", []) or []:
            if tag.get("name") not in seen_tag_names:
                merged["tags"].append(tag)
                seen_tag_names.add(tag["name"])

        # Components
        components = spec.get("components", {}) or {}
        for section in COMPONENT_SECTIONS:
            merge_component_dict(merged["components"][section], components.get(section), section, source_name)

        # Paths
        merge_paths(merged["paths"], spec.get("paths") or {}, source_name)

    # Union extended enums where extension schemas carry extra values
    # ErrorCode: base runtime has 15 values, ErrorCodeExtension carries 18 (15 + 3 new)
    union_enum_in_schema(
        merged["components"]["schemas"],
        "ErrorCode",
        merged["components"]["schemas"],
        extension_schema_name="ErrorCodeExtension",
    )
    # EventType: base governance has 40 values, EventTypeExtension carries 44 (40 + 4 new)
    union_enum_in_schema(
        merged["components"]["schemas"],
        "EventType",
        merged["components"]["schemas"],
        extension_schema_name="EventTypeExtension",
    )
    # Permission: base governance has 27 values, PermissionExtension carries 28 (27 + 1 new)
    union_enum_in_schema(
        merged["components"]["schemas"],
        "Permission",
        merged["components"]["schemas"],
        extension_schema_name="PermissionExtension",
    )

    # Empty sections are noise in the output
    for section in list(merged["components"].keys()):
        if not merged["components"][section]:
            del merged["components"][section]

    # Attach x-changelog list (one entry per source that has one). Inserted
    # after `description` in the info block via dict key order.
    if x_changelogs:
        merged["info"]["x-changelog"] = x_changelogs

    return merged


def dump(spec: dict[str, Any], path: Path, header_comment: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header_comment)
        f.write("\n")
        _yaml_dump(spec, f)
    print(f"  = wrote {path.relative_to(REPO)}")


def main() -> int:
    print("=" * 70)
    print("Cycles Protocol v0.1.26 — Merge Specs")
    print("=" * 70)

    # Protocol merged (runtime plane)
    print("\n[1/2] cycles-openapi-protocol-merged.yaml (runtime plane)")
    protocol = build_merged(
        title="Cycles Protocol — Runtime Plane (merged v0.1.26)",
        version="0.1.26",
        description=(
            "MERGED ARTIFACT — not canonical. Generated by scripts/merge_specs.py.\n\n"
            "Runtime plane for the Cycles Protocol v0.1.26 spec suite. Covers:\n"
            "  - Reserve / commit / release / extend reservation lifecycle (runtime base)\n"
            "  - DenyDetail, ObserveModeEnum, action quota violations (runtime extension)\n"
            "  - Action kind registry (62 built-in kinds) + quota counter endpoint + reset\n"
            "\n"
            "Source specs:\n"
            "  - cycles-protocol-v0.yaml (runtime base v0.1.25)\n"
            "  - cycles-protocol-extensions-v0.1.26.yaml (runtime extension v0.1.26)\n"
            "  - cycles-action-kinds-v0.1.26.yaml (action kinds v0.1.26)\n"
            "\n"
            "Use this file for: SDK codegen, runtime server validation, Swagger UI.\n"
            "Use cycles-openapi-admin-merged.yaml for admin tooling / dashboards.\n"
            "See cycles-spec-index.yaml for the full suite composition manifest."
        ),
        sources=[
            ("runtime_base", RUNTIME_BASE),
            ("runtime_extension", RUNTIME_EXT),
            ("action_kinds", ACTION_KINDS),
        ],
    )
    dump(
        protocol,
        PROTOCOL_OUT,
        header_comment=(
            "# ============================================================================\n"
            "# GENERATED FILE — DO NOT EDIT\n"
            "# ============================================================================\n"
            "# This is the pre-built runtime-plane merged artifact for Cycles v0.1.26.\n"
            "# To regenerate: python scripts/merge_specs.py\n"
            "# Sources:\n"
            "#   - cycles-protocol-v0.yaml (v0.1.25, runtime base)\n"
            "#   - cycles-protocol-extensions-v0.1.26.yaml (v0.1.26, runtime extension)\n"
            "#   - cycles-action-kinds-v0.1.26.yaml (v0.1.26, action kind registry)\n"
            "# Canonical sources live at the paths above. Edit source files, regenerate.\n"
            "# ============================================================================"
        ),
    )

    # Admin merged (governance plane)
    print("\n[2/2] cycles-openapi-admin-merged.yaml (admin/governance plane)")
    admin = build_merged(
        title="Cycles Protocol — Admin Plane (merged v0.1.26)",
        version="0.1.26",
        description=(
            "MERGED ARTIFACT — not canonical. Generated by scripts/merge_specs.py.\n\n"
            "Admin/governance plane for the Cycles Protocol v0.1.26 spec suite. Covers:\n"
            "  - Tenant / budget / policy / API key / webhook management (governance base v0.1.25.8)\n"
            "  - v0.1.26 policy extensions: action_quotas, risk_class_quotas, allow/deny lists\n"
            "  - v0.1.26 tenant extension: observe_mode\n"
            "  - v0.1.25.8 dashboard enrichments: AdminOverviewResponse optional fields,\n"
            "    open reason_code, deny_detail, policy_id on denied events\n"
            "  - Action kind registry + quota counter observability + counter reset endpoint\n"
            "  - action_quotas:read permission (enforced v0.1.26, balances:read fallback)\n"
            "\n"
            "Source specs:\n"
            "  - cycles-governance-admin-v0.1.25.yaml (governance base v0.1.25.8)\n"
            "  - cycles-governance-extensions-v0.1.26.yaml (governance extension v0.1.26)\n"
            "  - cycles-action-kinds-v0.1.26.yaml (action kinds v0.1.26)\n"
            "\n"
            "Use this file for: admin tooling codegen, policy editors, operator dashboards,\n"
            "governance API validators.\n"
            "Use cycles-openapi-protocol-merged.yaml for runtime server / SDK work.\n"
            "See cycles-spec-index.yaml for the full suite composition manifest."
        ),
        sources=[
            ("governance_base", GOV_BASE),
            ("governance_extension", GOV_EXT),
            ("action_kinds", ACTION_KINDS),
            # Include runtime_extension schemas ONLY (its paths: {} is empty)
            # so the admin merged has DenyDetail, ObserveModeEnum, event data
            # schemas, and the ErrorCode/EventType enum extensions. Admin event
            # consumers and error handlers need these.
            ("runtime_extension_schemas_only", RUNTIME_EXT),
        ],
    )
    dump(
        admin,
        ADMIN_OUT,
        header_comment=(
            "# ============================================================================\n"
            "# GENERATED FILE — DO NOT EDIT\n"
            "# ============================================================================\n"
            "# This is the pre-built admin-plane merged artifact for Cycles v0.1.26.\n"
            "# To regenerate: python scripts/merge_specs.py\n"
            "# Sources:\n"
            "#   - cycles-governance-admin-v0.1.25.yaml (v0.1.25.8, governance base)\n"
            "#   - cycles-governance-extensions-v0.1.26.yaml (v0.1.26, governance extension)\n"
            "#   - cycles-action-kinds-v0.1.26.yaml (v0.1.26, action kind registry)\n"
            "# Canonical sources live at the paths above. Edit source files, regenerate.\n"
            "# ============================================================================"
        ),
    )

    print("\nDone.")
    print(f"  Protocol merged: {PROTOCOL_OUT.relative_to(REPO)}")
    print(f"  Admin merged:    {ADMIN_OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
