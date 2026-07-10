# cycles-protocol-extensions — Changelog

Keep-a-Changelog format. Most recent first. Each entry corresponds to an `info.version` bump in `cycles-protocol-extensions-v0.1.26.yaml`.

New entries are added directly to this file. See `scripts/validate_changelogs.py` for the CI check that keeps this in sync with the spec.

---

## v0.1.27 — 2026-07-10

_(revision 2026-07-10 — ErrorCodeExtension base-list refresh against runtime 0.1.25.13)_

- **`ErrorCodeExtension` base list refreshed** against the canonical
  `ErrorCode` enum in `cycles-protocol-v0.yaml` revision 0.1.25.13. The
  reproduced base list had drifted: it lacked `LIMIT_EXCEEDED` (added to the
  base enum in runtime revision 0.1.25.12) and `TENANT_CLOSED` (added in
  runtime revision 0.1.25.13) while claiming "All v0.1.25 codes unchanged".
  Both codes are now present (before `INTERNAL_ERROR`, matching canonical
  order) and the description cites the base revision the list is reproduced
  from. The three v0.1.26 extension codes (`ACTION_QUOTA_EXCEEDED`,
  `ACTION_KIND_NOT_ALLOWED`, `ACTION_KIND_DENIED`) are unchanged.
- No extension wire-surface change — the extension adds the same three
  codes as before; this revision only corrects the reproduced base list
  (OpenAPI cannot express additive enum extension, so the full enum is
  restated and must track the base).
- **`DenyDetail.reason_code` known-values list re-aligned** with the base
  DecisionReasonCode documented values: adds `TENANT_CLOSED` (added to the
  base known values in runtime revision 0.1.25.13 for closed-tenant
  dry_run / decide denials); the base list is now described as seven
  values. Same alignment maintenance as the 2026-04-11 BUDGET_NOT_FOUND
  addition; reason codes remain an OPEN string, so this is
  documentation-only.

## v0.1.26 — 2026-04-11

_(2026-04-11 revision)_

- Aligned DenyDetail.reason_code documented known values with the
  base v0.1.25 DecisionReasonCode schema. Added BUDGET_NOT_FOUND
  to the known values list (it was missing). Reordered the list
  so the six base DecisionReasonCode values come first, followed
  by v0.1.26 additions and governance-context reasons.
- Added NORMATIVE "REASON CODE POPULATION" block to
  DecisionResponseExtension and ReservationCreateResponseExtension.
  Clarifies that v0.1.26 reason codes (ACTION_QUOTA_EXCEEDED,
  ACTION_KIND_DENIED, ACTION_KIND_NOT_ALLOWED) populate BOTH the
  base reason_code field AND deny_detail.reason_code. The base
  DecisionReasonCode schema was reopened in a coordinated base
  spec update (v0.1.25 revision, same date) from a closed enum
  to an open string with documented known values — specifically
  to enable this simple mirroring pattern without forcing
  extensions into awkward dual-field workarounds.
- RELATED BASE CHANGE: cycles-protocol-v0.yaml DecisionReasonCode
  was reopened. Clients MUST gracefully handle unknown reason_code
  values and MUST NOT reject them at strict validators.
- This is a documentation-only clarification in the extension;
  no wire format change, no version bump.

---

## v0.1.26 — 2026-04-09

Split from monolithic cycles-protocol-extensions-v0.1.26-final.yaml.
Runtime enforcement plane content only. Registry and governance
content moved to dedicated companion specs.
