# cycles-governance-extensions — Changelog

Keep-a-Changelog format. Most recent first. Each entry corresponds to an `info.version` bump in `cycles-governance-extensions-v0.1.26.yaml`.

New entries are added directly to this file. See `scripts/validate_changelogs.py` for the CI check that keeps this in sync with the spec.

---

## v0.1.27 — 2026-04-18

- Cross-surface correlation — adds `trace_id` (W3C Trace Context-
  compatible, `^[0-9a-f]{32}$`) as an OPTIONAL property on the
  redeclared `ErrorResponse` schema in this document. Syncs with the
  parallel additions in cycles-protocol-v0, cycles-governance-admin,
  and cycles-action-kinds so all four planes redeclare `ErrorResponse`
  with identical shape.

- Declares `X-Cycles-Trace-Id` AND `X-Request-Id` in this document's
  `components.headers`. Both are additive: this spec previously had
  zero response-header declarations, so OpenAPI tooling reading it in
  isolation could not surface the cross-surface correlation headers.
  Codifying both fixes that gap; the runtime plane was already able to
  emit `X-Request-Id` in practice, so this is documentation-tightening
  rather than a wire-level change.

- Adds a CORRELATION AND TRACING cross-reference paragraph at the top
  of `info.description` pointing readers to the authoritative contract
  in cycles-protocol-v0.yaml. Discoverability-only; no new normative
  content here.

- Backward compatibility: purely additive. Existing clients ignore the
  newly declared response headers and the new OPTIONAL schema property.

---

## v0.1.26 — 2026-04-09

Split from monolithic cycles-protocol-extensions-v0.1.26-final.yaml.
Governance/admin plane content only.
