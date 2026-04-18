# cycles-action-kinds — Changelog

Keep-a-Changelog format. Most recent first. Each entry corresponds to an `info.version` bump in `cycles-action-kinds-v0.1.26.yaml`.

New entries are added directly to this file. See `scripts/validate_changelogs.py` for the CI check that keeps this in sync with the spec.

---

## v0.1.27 — 2026-04-18

- Cross-surface correlation — adds `trace_id` (W3C Trace Context-
  compatible, `^[0-9a-f]{32}$`) as an OPTIONAL property on the
  redeclared `ErrorResponse` schema in this document. Syncs with the
  parallel additions in cycles-protocol-v0, cycles-governance-admin,
  and cycles-governance-extensions so all four planes redeclare
  `ErrorResponse` with identical shape.

- Declares `X-Cycles-Trace-Id` in this document's `components.headers`
  and references it from every response that currently references
  `X-Request-Id` (listActionKinds 200, getActionKind 200, and the two
  admin counter endpoints). OpenAPI tooling reading this spec in
  isolation now sees the cross-surface correlation header.

- Adds a CORRELATION AND TRACING cross-reference paragraph at the top
  of `info.description` pointing readers to the authoritative contract
  in cycles-protocol-v0.yaml. Discoverability-only; no new normative
  content here.

- The embedded `x-action-kind-registry.version` stays at `"0.1.26"` —
  the action-kind taxonomy itself is unchanged. Only the spec document
  revision bumps.

- Backward compatibility: purely additive. Existing clients ignore the
  new response header and the new OPTIONAL schema property.

---

## v0.1.26 — 2026-04-09

- Split from cycles-protocol-extensions-v0.1.26-final.yaml monolith.
- Expanded registry from 44 to 62 built-in kinds.
- NEW categories: agent (4 kinds), memory (3 kinds),
  reasoning (2 kinds), vision (3 kinds).
- NEW kinds in existing categories: vector.delete,
  llm.structured_output, code.lint, document.edit,
  message.chat.post, http.graphql.
- Added mcp_tool_prefixes to llm.completion and llm.embedding
  (previously empty).
- Added RiskClassQuota, per_minute_tumbling window, threshold_pct.
- per_run_counter_ttl_ms field added to ActionQuota.
- Calendar-bucket window model fully specified and consistent
  throughout (no first-write+TTL contradictions).
- REGISTRY GOVERNANCE: added normative sections for deprecation
  process, provider aliasing policy, adding new built-in kinds,
  and custom.* namespace rules.
- DOCUMENTATION TIGHTENING (no wire change):
  POST /v1/admin/action-quota-counters/reset is documented as
  AdminKeyAuth-only — the previous prose mentioned an ApiKeyAuth
  branch with a reserved `action_quotas:write` permission, but the
  operation's `security:` block was already AdminKeyAuth-only and
  no `action_quotas:write` permission exists in v0.1.26.
  ActionQuotaCounterResetRequest.tenant_id description tightened
  from "Ignored when using ApiKeyAuth" to "REQUIRED" — same
  rationale (the AdminKeyAuth-only `security:` block already
  mandated this; correctly-implemented servers were already
  requiring tenant_id). Servers MUST return 400 INVALID_REQUEST
  (`missing_required_field: tenant_id`) when tenant_id is omitted.
