# cycles-protocol-extensions — Changelog

Keep-a-Changelog format. Most recent first. Each entry corresponds to an `info.version` bump in `cycles-protocol-extensions-v0.1.26.yaml`.

New entries are added directly to this file. See `scripts/validate_changelogs.py` for the CI check that keeps this in sync with the spec.

---

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
