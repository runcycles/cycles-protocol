# Cycles → APS Tier-1 denial reason mapping (v0.1 draft)

**Status:** DRAFT. Sister artifact to `drafts/cycles-evidence-v0.1.yaml`.

**Purpose:** Specifies the contract for `mapCyclesDenialToFoundation()` —
the function the APS-side Cycles adapter at
`src/v2/payment-rails/cycles/index.ts` (in `aeoess/agent-passport-system`)
will implement to translate Cycles denial signals into APS PaymentReceipt
Tier-1 `denial_reason` values.

The mapping is intentionally **lossy by design**: Cycles emits 15
`ErrorCode` values and 6 known `DecisionReasonCode` values, and APS
Tier-1 is a closed 6-value enum. The richer Cycles-specific detail is
preserved Tier-2 in the `cycles.denial_detail` namespace per
`aeoess/agent-passport-system#25` (comments 4413731054, 4422627045).

## Scope

This doc covers the **v0.1.25 base protocol surface only.** The
`cycles-protocol-extensions-v0.1.26.yaml` extension spec is published
in the repo but **not yet implemented in any Cycles deployment**, so
its three additional ErrorCodes / DecisionReasonCodes
(`ACTION_QUOTA_EXCEEDED`, `ACTION_KIND_DENIED`,
`ACTION_KIND_NOT_ALLOWED`) and the v0.1.26 `DenyDetail` structure are
treated as v0.2 promotion criteria — see the dedicated section below.
Including v0.1.26 mappings now would document a contract that no
deployment exercises and no fixture can verify against.

## Source references

| Layer | Source | Lines |
|---|---|---|
| Cycles `ErrorCode` (closed, 15 values) | `cycles-protocol-v0.yaml` | 429-446 |
| Cycles `DecisionReasonCode` (open string, 6 known values in v0.1.25 base) | `cycles-protocol-v0.yaml` | 487-545 |
| APS Tier-1 `denial_reason` (closed, 6 values) | `aeoess/agent-passport-system#25` comment 4422182941 (citing the APS Tier-1 enum) | n/a |
| Per-row note requirement (lossy compression must be explicit) | `aeoess/agent-passport-system#25` comment 4422627045 | n/a |

The mapping uses ONLY the six closed APS Tier-1 values:

  - `no_commerce_scope`
  - `spend_limit_exceeded`
  - `wallet_revoked`
  - `time_window_violation`
  - `rail_error`
  - `requires_owner_confirmation`

A conformant implementation MUST NOT invent new Tier-1 values. The
closed taxonomy is enforced on three axes in `aeoess/agent-passport-system`:

  - `DenialReason` is a closed string-literal TypeScript union in
    `src/v2/payment-rails/types.ts`.
  - `VALID_DENIAL_REASONS` is the runtime array in
    `src/v2/payment-rails/hooks.ts:87-94` — the same six strings.
  - `emitDenial` (`hooks.ts:381`) and the two verifier paths
    (`hooks.ts:606`, `hooks.ts:629`) all reject values outside this
    set with `INVALID_DENIAL_REASON`.

## Mapping table 1 — Cycles `ErrorCode` → APS Tier-1

Surfaces on 4xx/5xx HTTP responses from any of the four Cycles runtime
endpoints. In the CyclesEvidence envelope, these appear in
`payload.error.response.error` (see `drafts/cycles-evidence-v0.1.yaml`
`ErrorResponseMirror`).

| Cycles `ErrorCode` | HTTP class | APS Tier-1 | Compression notes |
|---|---|---|---|
| `INVALID_REQUEST` | 4xx | `rail_error` | Malformed request — rail-side validation failure. Not a budget/scope/wallet semantic; nearest fit is `rail_error`. |
| `UNAUTHORIZED` | 4xx | `rail_error` | Authentication failure at the Cycles rail. APS has its own auth layer above; this is the downstream rail saying "you didn't auth to me." Not `no_commerce_scope` because that's a scope/policy mismatch, not an auth failure. |
| `FORBIDDEN` | 4xx | `no_commerce_scope` | Per canonical L1356: "subject.tenant MUST match the effective tenant derived from auth; otherwise the server MUST return 403 FORBIDDEN." The APS analog is "this delegation doesn't grant scope to this rail's tenancy." |
| `NOT_FOUND` | 4xx | `rail_error` | Generic NOT_FOUND is rail-internal (e.g., reservation_id not on the ledger). Lossy: when the missing thing is structurally the wallet, the underlying semantic IS `wallet_revoked`, but the wire signal doesn't tell us that — defaulting to `rail_error` keeps APS receipts conservative. |
| `BUDGET_EXCEEDED` | 409 | `spend_limit_exceeded` | The clean one. This is the canonical non-dry reserve denial path that motivates the whole integration (issue #25). |
| `BUDGET_FROZEN` | 409 | `wallet_revoked` | Operator-set FROZEN status on a budget is semantically equivalent to a revoked wallet — the holder can no longer spend until manual reconciliation. |
| `BUDGET_CLOSED` | 409 | `wallet_revoked` | Permanently closed budget — terminal revocation. Same Tier-1 as `BUDGET_FROZEN`; the closed-vs-frozen distinction is preserved Tier-2 in `cycles.denial_detail.code`. |
| `RESERVATION_EXPIRED` | 409 | `time_window_violation` | Direct semantic match — TTL elapsed. Explicitly called out as "clean" by aeoess in issue #25 (comment 4422627045). |
| `RESERVATION_FINALIZED` | 409 | `rail_error` | Attempting to commit/release an already-finalized reservation — rail-state error, not a Tier-1-mappable user-facing reason. |
| `IDEMPOTENCY_MISMATCH` | 409 | `rail_error` | Idempotency key replay collision — rail-internal concern. |
| `UNIT_MISMATCH` | 409 | `rail_error` | Commit `actual.unit` doesn't match reservation `reserved.unit` — rail-internal concern. |
| `OVERDRAFT_LIMIT_EXCEEDED` | 409 | `spend_limit_exceeded` | Out of budget plus exhausted overdraft allowance — semantically still "spend limit exceeded." The overdraft-specific detail is preserved Tier-2 in `cycles.denial_detail.code`. |
| `DEBT_OUTSTANDING` | 409 | `wallet_revoked` | Debt > 0 locks the scope from new reservations until reconciled — equivalent to a temporarily revoked wallet. Some implementations may prefer mapping this to `spend_limit_exceeded`; the `wallet_revoked` choice matches the canonical L900 framing of debt as a state-machine-level block, not a balance-level block. |
| `MAX_EXTENSIONS_EXCEEDED` | 409 | `time_window_violation` | The reservation has been extended too many times — temporal-window concern. |
| `INTERNAL_ERROR` | 5xx | `rail_error` | Server-side error — by definition rail-side. |

## Mapping table 2 — Cycles `DecisionReasonCode` → APS Tier-1

Surfaces on 200 OK responses with `decision: DENY` (i.e., `/v1/decide`
pre-checks and `dry_run: true` reserves). In the CyclesEvidence envelope,
these appear in `payload.decide.response.reason_code` or
`payload.reserve.response.reason_code`.

`DecisionReasonCode` is an **open string** per canonical L496-L505;
unknown values MUST gracefully degrade to a generic DENY treatment.
The mapping below covers all 6 known values from the v0.1.25 base.

| Cycles `DecisionReasonCode` | APS Tier-1 | Compression notes |
|---|---|---|
| `BUDGET_EXCEEDED` | `spend_limit_exceeded` | Same as ErrorCode counterpart — this is the `/v1/decide` and dry-run version of the same condition. |
| `BUDGET_FROZEN` | `wallet_revoked` | Same as ErrorCode counterpart. |
| `BUDGET_CLOSED` | `wallet_revoked` | Same as ErrorCode counterpart. |
| `BUDGET_NOT_FOUND` | `rail_error` | No budget exists for the requested `(scope, unit)` — rail-side configuration gap, not a user-facing Tier-1 reason. NOTE: on non-dry reserve and `/v1/events`, the same underlying condition surfaces as HTTP 404 `NOT_FOUND` instead (per canonical L514-L516), which maps to `rail_error` via Table 1. The two-paths-same-Tier-1 outcome is intentional. |
| `OVERDRAFT_LIMIT_EXCEEDED` | `spend_limit_exceeded` | Same as ErrorCode counterpart. |
| `DEBT_OUTSTANDING` | `wallet_revoked` | Same as ErrorCode counterpart. |

### v0.1.26 extension is out of scope for v0.1

`cycles-protocol-extensions-v0.1.26.yaml` defines three additional
codes that surface both as ErrorCode (L516-L543, MUST-add to the
ErrorCode enum) and as DecisionReasonCode (L520, alongside `DenyDetail`
at L530-L532):

  - `ACTION_QUOTA_EXCEEDED` — per-action-kind or risk-class quota hit
  - `ACTION_KIND_DENIED` — action kind in `denied_action_kinds`
  - `ACTION_KIND_NOT_ALLOWED` — action kind not in `allowed_action_kinds`

**The extension spec is published but not yet implemented in any
Cycles deployment.** Mapping it now would document a contract no
deployment exercises and no fixture can verify against. v0.1 of this
doc deliberately excludes the extension from both mapping tables and
from the reference implementation to keep the contract honest about
what real envelopes will carry.

The sister `drafts/cycles-evidence-v0.1.yaml` `ErrorResponseMirror.error`
enum is correspondingly fixed to the 15 v0.1.25 base values, and the
response mirrors have `additionalProperties: false` (no `deny_detail`
field). Both reflect the same v0.1.25-only scope.

**v0.2 promotion criterion.** When a Cycles deployment ships with
the v0.1.26 extension implemented, the v0.2 revision of this doc
will:

  1. Add three rows to mapping table 1 (extension ErrorCodes on the
     live non-dry path, mapping to `spend_limit_exceeded` /
     `no_commerce_scope` / `no_commerce_scope` respectively).
  2. Add three rows to mapping table 2 (same codes via DecisionReasonCode
     on `/v1/decide` and dry-run reserve), with identical Tier-1
     mappings for cross-path consistency.
  3. Add a `deny_detail` field to the CyclesEvidence response mirrors
     and define a `cycles.denial_detail.deny_detail` Tier-2 ride-along
     shape carrying the v0.1.26 `DenyDetail` structure.
  4. Add at least one fixture exercising the extension end-to-end.

Until those conditions are met, the v0.1 adapter handles only the
15 base ErrorCodes and 6 base DecisionReasonCodes documented above.

### Unknown `DecisionReasonCode` values

Per canonical L503-L505: "Clients MUST gracefully handle unknown values
— log them and map to generic DENY handling (i.e., 'the request was
denied; treat as a terminal failure even if we don't recognize the
specific reason')."

The adapter MUST mirror this rule: any reason_code outside the 9 known
values maps to `rail_error` (the most conservative Tier-1 mapping for
"we got a DENY but don't recognize the specific reason"). The raw
reason_code MUST still be preserved Tier-2 in
`cycles.denial_detail.code` so audit consumers retain the unrecognized
value byte-for-byte.

## APS Tier-1 reasons with no Cycles source

`requires_owner_confirmation` has **no Cycles counterpart**. The Cycles
model is deterministic decide / reserve / commit / release; there is
no "user confirmation required" intermediate state. No `ErrorCode` or
`DecisionReasonCode` value will ever map to this Tier-1 reason.

This is documented forward-compat: if a future Cycles minor version
adds a `REQUIRES_OWNER_CONFIRMATION` style decision/error
(unlikely — the integration model assumes Cycles is downstream of the
agent's auth/policy layer), this mapping doc gets a row.

## Tier-2 detail preservation (`cycles.denial_detail`)

The lossy compression above only applies at the APS receipt's Tier-1
`denial_reason` field. The full Cycles signal is preserved Tier-2 under
the `cycles.denial_detail` namespace per `aeoess/agent-passport-system#25`:

Example shape (ErrorCode-sourced denial):

```json
{
  "denial_reason": "spend_limit_exceeded",
  "cycles": {
    "denial_detail": {
      "layer": "cycles",
      "source": "ErrorCode",
      "code": "BUDGET_EXCEEDED",
      "http_status": 409,
      "message": "Insufficient remaining budget for scope tenant=acme",
      "request_id": "req_01H...",
      "trace_id": "0af7651916cd43dd8448eb211c80319c"
    }
  }
}
```

The `source` field carries `"ErrorCode"` for 4xx/5xx-sourced denials
or `"DecisionReasonCode"` for 2xx-DENY-sourced denials; ErrorCode-source
envelopes additionally carry `http_status`, `message`, and `request_id`
from the canonical `ErrorResponse` body, while DecisionReasonCode-source
envelopes have only `code` and `trace_id` (the canonical
`DecisionResponse` / `ReservationCreateResponse` body carries no
`request_id` or `http_status`).

The Tier-2 fields populate from the CyclesEvidence
`payload.error.response.*` (for ErrorCode source) or
`payload.decide.response.*` / `payload.reserve.response.*` (for
DecisionReasonCode source) depending on where the denial surfaced.

## TypeScript reference implementation

The shape below maps directly into the adapter at
`src/v2/payment-rails/cycles/index.ts`. The mapping is a pure
data-driven lookup; the rules above are encoded in two const tables and
one function.

```typescript
import type { CyclesEvidence } from './evidence-envelope';
import type { DenialReason } from '../types';

// Local return shape: Tier-1 reason + Tier-2 cycles.denial_detail
// ride-along. The actual emit path (emitDenial in hooks.ts) consumes
// `denial_reason` directly; the `cycles` namespace is attached to the
// PaymentDenialReceipt envelope by the caller before signing.
interface FoundationDenialMapping {
  denial_reason: DenialReason;
  cycles: {
    denial_detail: {
      layer: 'cycles';
      source: 'ErrorCode' | 'DecisionReasonCode';
      code: string;
      http_status?: number;
      message?: string;
      request_id?: string;
      trace_id?: string;
    };
  };
}

// Cycles ErrorCode — 15 v0.1.25 base values, canonical
// cycles-protocol-v0.yaml L429-L446. The v0.1.26 extension is OUT
// OF SCOPE for v0.1 (not yet implemented in any deployment); v0.2
// will add ACTION_QUOTA_EXCEEDED / ACTION_KIND_DENIED /
// ACTION_KIND_NOT_ALLOWED.
const ERROR_CODE_TO_TIER1: Record<string, DenialReason> = {
  INVALID_REQUEST:           'rail_error',
  UNAUTHORIZED:              'rail_error',
  FORBIDDEN:                 'no_commerce_scope',
  NOT_FOUND:                 'rail_error',
  BUDGET_EXCEEDED:           'spend_limit_exceeded',
  BUDGET_FROZEN:             'wallet_revoked',
  BUDGET_CLOSED:             'wallet_revoked',
  RESERVATION_EXPIRED:       'time_window_violation',
  RESERVATION_FINALIZED:     'rail_error',
  IDEMPOTENCY_MISMATCH:      'rail_error',
  UNIT_MISMATCH:             'rail_error',
  OVERDRAFT_LIMIT_EXCEEDED:  'spend_limit_exceeded',
  DEBT_OUTSTANDING:          'wallet_revoked',
  MAX_EXTENSIONS_EXCEEDED:   'time_window_violation',
  INTERNAL_ERROR:            'rail_error',
};

// Cycles DecisionReasonCode — 6 known v0.1.25 base values (open string
// per canonical L487). v0.1.26 extension values are OUT OF SCOPE; see
// note above ERROR_CODE_TO_TIER1.
const DECISION_REASON_TO_TIER1: Record<string, DenialReason> = {
  BUDGET_EXCEEDED:          'spend_limit_exceeded',
  BUDGET_FROZEN:            'wallet_revoked',
  BUDGET_CLOSED:            'wallet_revoked',
  BUDGET_NOT_FOUND:         'rail_error',
  OVERDRAFT_LIMIT_EXCEEDED: 'spend_limit_exceeded',
  DEBT_OUTSTANDING:         'wallet_revoked',
};

/**
 * Map a Cycles denial signal (extracted from a CyclesEvidence envelope)
 * to an APS Tier-1 denial reason, preserving the full Cycles-side
 * detail in the Tier-2 `cycles.denial_detail` namespace.
 *
 * Returns `null` if the evidence envelope does not represent a denial
 * (artifact_type ∉ {error, decide-DENY, reserve-DENY}); callers should
 * NOT invoke this on permit-class evidence.
 */
export function mapCyclesDenialToFoundation(
  evidence: CyclesEvidence,
): FoundationDenialMapping | null {
  const p = evidence.payload;

  // Path A: HTTP 4xx/5xx error envelope.
  if (p.error) {
    const { error: code, message, request_id, trace_id } = p.error.response;
    return {
      denial_reason: ERROR_CODE_TO_TIER1[code] ?? 'rail_error',
      cycles: {
        denial_detail: {
          layer: 'cycles',
          source: 'ErrorCode',
          code,
          http_status: p.error.http_status,
          message,
          request_id,
          trace_id,
        },
      },
    };
  }

  // Path B: 2xx DecisionResponse with decision: DENY (either /decide
  // or dry_run: true reserve).
  const denyResponse =
    p.decide?.response.decision === 'DENY' ? p.decide.response :
    p.reserve?.response.decision === 'DENY' ? p.reserve.response :
    null;

  if (denyResponse) {
    const code = denyResponse.reason_code ?? 'UNKNOWN';
    return {
      denial_reason: DECISION_REASON_TO_TIER1[code] ?? 'rail_error',
      cycles: {
        denial_detail: {
          layer: 'cycles',
          source: 'DecisionReasonCode',
          code,
          trace_id: evidence.trace_id,
        },
      },
    };
  }

  // Permit-class evidence — caller should not have invoked us here.
  return null;
}
```

## Round-trip verification

The CyclesEvidence reference fixtures at
`drafts/fixtures/cycles-evidence-v0.1/cases/` cover the denial-path
inputs this function consumes:

| Fixture | Denial source | Expected Tier-1 |
|---|---|---|
| `03-reserve-dry-run-deny.json` | DecisionReasonCode: `BUDGET_EXCEEDED` | `spend_limit_exceeded` |
| `11-reserve-live-budget-exceeded.json` | ErrorCode: `BUDGET_EXCEEDED` | `spend_limit_exceeded` |
| `12-decide-live-forbidden.json` | ErrorCode: `FORBIDDEN` | `no_commerce_scope` |

These three fixtures should be the **golden test cases** for the
adapter's denial-mapping unit tests. They prove both the Tier-1
compression and the Tier-2 detail preservation work end-to-end against
real signed envelopes — a verifier that holds the public key can
recover the canonical Cycles denial code byte-for-byte from
`cycles.denial_detail.code` and compare it back to the signed evidence.

## Promotion path

This doc lives under `drafts/` for review and external feedback. It
will move to a numbered spec file at repo root (e.g.
`cycles-aps-denial-mapping-v0.2.md`) once:

  1. The APS-side adapter (`src/v2/payment-rails/cycles/index.ts` in
     `aeoess/agent-passport-system`) ships with this mapping implemented.
  2. The APS-side SDK PR adding `rail.budget_reservation.{permit,release,denial}.v1`
     literals has merged (committed-to but not yet open as of this
     draft per `aeoess/agent-passport-system#25` comment 4433715146).
  3. End-to-end test coverage demonstrates the round-trip: a Cycles
     denial → CyclesEvidence envelope → APS PaymentReceipt with the
     mapped Tier-1 reason and intact Tier-2 detail, verifiable offline.

Until those land, this doc is the canonical reference for the mapping
contract that the future adapter will implement.
