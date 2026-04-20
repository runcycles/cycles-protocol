# Cycles Protocol Conformance

This document is the authoritative statement of what a Cycles implementation MUST, SHOULD, and MAY do to claim conformance with the Cycles Protocol.

**Current conformance target:** **v0.1.25** (runtime base + governance-admin cross-plane surface). This is the version runcycles' own reference servers implement today and the version against which a second implementation can be validated.

**Upcoming conformance target:** **v0.1.26** (action-kind registry, runtime extensions, governance extensions). These specs are published in this repo but are **not yet required for conformance**; implementations SHOULD plan for them. They will be promoted to MUST in a future revision of this document once the reference stack implements them.

**Authoritative sources (v0.1.25):**

1. all files enumerated in [`cycles-spec-index.yaml`](cycles-spec-index.yaml) under `conformance: normative` **at or below v0.1.25** (currently `cycles-protocol-v0.yaml`), and
2. any schemas or operations inside `conformance: mixed` documents (currently `cycles-governance-admin-v0.1.25.yaml`) that are individually labeled `x-conformance: normative`.

Language follows [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119): MUST / MUST NOT / SHOULD / SHOULD NOT / MAY.

---

## Summary

Cycles is a **minimum protocol**. A conformant v0.1.25 server exposes approximately 17 operations — 9 runtime reserve/commit/release/decide/balances/events operations plus 8 cross-plane event / webhook / auth-introspection operations — and is otherwise free to implement tenant management, budget provisioning, key rotation, and audit UX however it likes.

| File | Target | Conformance | What it defines |
|---|---|---|---|
| [`cycles-protocol-v0.yaml`](cycles-protocol-v0.yaml) | v0.1.25 | normative | Runtime base: reserve / commit / release / decide / balances / events |
| [`cycles-governance-admin-v0.1.25.yaml`](cycles-governance-admin-v0.1.25.yaml) | v0.1.25 | mixed | Mostly reference admin API (runcycles' management plane; implementers MAY diverge). Eight cross-plane operations and a set of schemas inside this file are normative — see §MUST below. |
| [`cycles-action-kinds-v0.1.26.yaml`](cycles-action-kinds-v0.1.26.yaml) | v0.1.26 | upcoming | Action-kind registry + quota primitives. SHOULD today; MUST once v0.1.26 is the active target. |
| [`cycles-protocol-extensions-v0.1.26.yaml`](cycles-protocol-extensions-v0.1.26.yaml) | v0.1.26 | upcoming | DenyDetail, ObserveMode, v0.1.26 evaluation order, v0.1.26 schemas. SHOULD today. |
| [`cycles-governance-extensions-v0.1.26.yaml`](cycles-governance-extensions-v0.1.26.yaml) | v0.1.26 | upcoming | Policy fields for action quotas / access control; tenant observe_mode. SHOULD today. |

Operations inside v0.1.26 files still carry `x-conformance: normative` — that label describes each operation's contract *within its own spec*. Whether the spec is currently required for conformance is a separate question, answered by "current conformance target" above.

---

## MUST — required for v0.1.25 conformance

A conformant implementation MUST:

### Runtime operations (`cycles-protocol-v0.yaml`)

Implement and honor the semantics of all 9 runtime operations:

1. `POST /v1/reservations` — **createReservation**
2. `GET /v1/reservations` — **listReservations** (optional recovery/debug endpoint; still part of the protocol surface)
3. `GET /v1/reservations/{reservation_id}` — **getReservation**
4. `POST /v1/reservations/{reservation_id}/commit` — **commitReservation**
5. `POST /v1/reservations/{reservation_id}/release` — **releaseReservation**
6. `POST /v1/reservations/{reservation_id}/extend` — **extendReservation**
7. `POST /v1/decide` — **decide** (soft-landing decision preview)
8. `GET /v1/balances` — **getBalances**
9. `POST /v1/events` — **createEvent** (direct settlement path)

### Core invariants

- **Atomic reservation** — budget is locked across all affected scopes in one step; no partial locks.
- **Concurrency-safe enforcement** — shared budgets MUST NOT be oversubscribed under concurrent reserve calls.
- **Idempotent commit and release** — retries MUST be safe; the same action MUST NOT settle twice.
- **Unit consistency** — every reserve / commit / release / event operation MUST validate and preserve unit denomination.

### Error semantics

Return the exact HTTP status + `error` code pairs defined in `cycles-protocol-v0.yaml` §ERROR SEMANTICS — including `BUDGET_EXCEEDED` (409), `OVERDRAFT_LIMIT_EXCEEDED` (409), `IDEMPOTENCY_MISMATCH` (409), `RESERVATION_FINALIZED` (409), `RESERVATION_EXPIRED` (410), `UNIT_MISMATCH` (400), `NOT_FOUND` (404), and `DEBT_OUTSTANDING` (409). The v0.1.26 action-governance error codes (`ACTION_QUOTA_EXCEEDED`, `ACTION_KIND_NOT_ALLOWED`, `ACTION_KIND_DENIED`) are upcoming and listed under §Upcoming below.

### Authentication & tenancy

Authenticate via `X-Cycles-API-Key` header and enforce tenant isolation per `cycles-protocol-v0.yaml` §AUTH & TENANCY. How API keys are provisioned, rotated, or scoped to permissions is implementation-specific.

### Cross-plane operations and schemas (currently in `cycles-governance-admin-v0.1.25.yaml`)

Although `cycles-governance-admin-v0.1.25.yaml` is mostly reference (the tenant / budget / policy / API-key / audit CRUD is runcycles' own shape), **eight operations and a set of schemas in that file are normative** because they expose the protocol's event stream, webhook delivery contract, and balance / auth introspection surface across planes. Each carries an explicit `x-conformance: normative` label.

Normative operations (8):

1. `GET /v1/admin/events` — **listEvents**
2. `GET /v1/admin/events/{event_id}` — **getEvent**
3. `POST /v1/admin/webhooks/{subscription_id}/replay` — **replayEvents**
4. `GET /v1/events` — **listTenantEvents** (tenant-scoped)
5. `GET /v1/admin/webhooks/{subscription_id}/deliveries` — **listWebhookDeliveries**
6. `GET /v1/webhooks/{subscription_id}/deliveries` — **listTenantWebhookDeliveries** (tenant-scoped)
7. `GET /v1/balances` — **getBalances** (admin-plane view of the same path served by the runtime base)
8. `GET /v1/auth/introspect` — **introspectAuth**

Normative schemas:

- `Event`, `EventType`, and all `EventData*` payload variants
- `WebhookDelivery` envelope, signature header rules, and retry semantics (`WebhookRetryPolicy`)
- `Permission` enum
- shared `Amount`, `Subject`, `Balance` (originate in `cycles-protocol-v0.yaml`; re-referenced here)

Any events emitted MUST conform to the `EventType` enum and `EventData*` payload schemas; any webhooks delivered MUST match the `WebhookDelivery` envelope shape, signature header rules, and retry semantics.

> **Transitional**: these operations and schemas currently live inside `cycles-governance-admin-v0.1.25.yaml`. A future revision will extract the event and webhook content into dedicated `cycles-events-v0.yaml` and `cycles-webhooks-v0.yaml` files. The contract is normative regardless of file location.

---

## SHOULD — strongly recommended

A conformant implementation SHOULD:

- Emit events for budget-state changes (reservation.*, budget.*, quota.*) matching the `EventType` enum. Implementations MAY sample or filter which events they emit, but emitted events MUST follow the schema.
- Propagate `X-Cycles-Trace-Id` and W3C `traceparent` headers per `cycles-protocol-v0.yaml` §CORRELATION AND TRACING. Trace correlation is central to multi-service debugging.
- Implement `POST /v1/decide` even though it's optional in v0 — agent frameworks need soft-landing signals for graceful degradation.
- Expose `GET /v1/balances` for operator visibility into remaining budget per scope.
- Publish metrics / logs when scopes enter `is_over_limit: true` state so operators can reconcile.

### Upcoming (v0.1.26) — SHOULD today, MUST once promoted

These specs are published in this repo but are **not yet required for conformance**. runcycles' reference servers do not implement them yet. A conformant implementation SHOULD plan for them; they will become MUST in a future revision of this document once the reference stack ships support.

- **Action-kind registry** (`cycles-action-kinds-v0.1.26.yaml`) — 4 operations:
  1. `GET /v1/action-kinds` — **listActionKinds**
  2. `GET /v1/action-kinds/{kind}` — **getActionKind**
  3. `GET /v1/admin/action-quota-counters` — **listActionQuotaCounters**
  4. `POST /v1/admin/action-quota-counters/reset` — **resetActionQuotaCounter**
- **Runtime extensions** (`cycles-protocol-extensions-v0.1.26.yaml`) — no new paths; adds `DenyDetail`, `ObserveMode`, the full reservation evaluation order (access control → risk-class quotas → per-kind quotas → budget), and the new error codes `ACTION_QUOTA_EXCEEDED`, `ACTION_KIND_NOT_ALLOWED`, `ACTION_KIND_DENIED`.
- **Governance extensions** (`cycles-governance-extensions-v0.1.26.yaml`) — 2 PATCH operations (`updateTenantObserveMode`, `updatePolicyActionQuotas`) and the policy field contracts (`action_quotas`, `risk_class_quotas`, `allowed_action_kinds`, `denied_action_kinds`, tenant `observe_mode`). The PATCH endpoints MAY be replaced by an equivalent mechanism (config file, direct DB write), but once v0.1.26 is the active target the **field contracts** MUST be evaluated at reserve time per `cycles-protocol-extensions-v0.1.26.yaml` §RESERVATION EVALUATION ORDER.

---

## MAY — implementation choice

A conformant implementation MAY:

- Adopt the shape of `cycles-governance-admin-v0.1.25.yaml` (tenants, budgets, policies, API keys, audit, webhook subscriptions, bulk operations) wholesale, as runcycles does.
- Replace any or all of those reference portions with an alternative provisioning mechanism: OAuth/OIDC for auth, GitOps YAML for policies, internal admin console for tenants, direct DB writes for budget allocation, etc. (The reference portions only — the eight normative cross-plane operations listed under §MUST still apply.)
- Skip `audit_log` entirely. Not required by the protocol.
- Expose additional endpoints beyond those specified, as long as they use a non-`/v1` path prefix or a vendor-namespaced extension path (e.g., `/v1/x-runcycles/...`).

---

## How to verify conformance

A Cycles conformance test kit (a set of black-box curl/pytest probes any server can be pointed at) is planned but **not yet published**. Until it exists, conformance is asserted by:

1. Validating your OpenAPI descriptor against `merged/cycles-openapi-protocol-merged.yaml` using any OpenAPI 3.1.0 validator.
2. Passing the Spectral ruleset in [`.spectral.yaml`](.spectral.yaml) on your own spec.
3. Running the runcycles reference Python/TypeScript/Rust clients against your server's `/v1/reservations` endpoints and verifying expected ALLOW / DENY / error behavior.

A dedicated conformance kit is tracked for a future release. Contributions welcome.

---

## Questions and feedback

Open an issue or discussion in [runcycles/cycles-protocol](https://github.com/runcycles/cycles-protocol).
