# Cycles Protocol Conformance

This document is the authoritative statement of what a Cycles implementation MUST, SHOULD, and MAY do to claim conformance with the Cycles Protocol.

**Current conformance target:** **v0.1.25** (runtime base + governance-admin cross-plane surface). This is the version runcycles' own reference servers implement today and the version against which a second implementation can be validated.

**Upcoming conformance target:** **v0.1.26** (action-kind registry, runtime extensions, governance extensions). These specs are published in this repo but are **not yet required for conformance**; implementations SHOULD plan for them. They will be promoted to MUST in a future revision of this document once the reference stack implements them.

**Authoritative sources (v0.1.25):**

1. all files enumerated in [`cycles-spec-index.yaml`](cycles-spec-index.yaml) under `conformance: normative` **at or below v0.1.25** (currently `cycles-protocol-v0.yaml`),
2. inside `conformance: mixed` documents (currently `cycles-governance-admin-v0.1.25.yaml`): the operations individually labeled `x-conformance: normative`, and the schemas designated normative by being enumerated in this document's §MUST "Normative schemas" list (schemas in that spec are **not** `x-conformance`-labeled — only operations carry that label; a schema's normative status is established by the enumeration here), and
3. any **cross-plane normative invariant** declared as such in a normative-or-mixed document — a property of persisted state or protocol behavior that binds regardless of which operation or provisioning mechanism produces it (e.g. the `WEBHOOK SUBSCRIPTION INVARIANTS` block in `cycles-governance-admin-v0.1.25.yaml` `info.description`). These invariants are first-class members of the normative surface alongside named schemas and `x-conformance: normative` operations; a server MUST uphold them even where the producing operation is `x-conformance: reference`.

Language follows [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119): MUST / MUST NOT / SHOULD / SHOULD NOT / MAY.

---

## Summary

Cycles is a **minimum protocol**. A conformant v0.1.25 server MUST implement 12 operations (4 core runtime reserve/commit/release/extend + 8 cross-plane event / webhook / auth-introspection; `getBalances` is cross-plane MUST because the admin spec re-declares the runtime's "nice-to-have" path as normative), MUST honor the normative schemas and the cross-plane invariants (the `WEBHOOK SUBSCRIPTION INVARIANTS` — see §MUST), and SHOULD implement an additional 4 runtime operations (decide, listReservations, getReservation, createEvent) that the spec marks OPTIONAL but that well-rounded servers expose. Total v0.1.25 protocol surface is 16 distinct operations plus those schema + invariant contracts. The server is otherwise free to implement tenant management, budget provisioning, key rotation, and audit UX however it likes.

| File | Target | Conformance | What it defines |
|---|---|---|---|
| [`cycles-protocol-v0.yaml`](cycles-protocol-v0.yaml) | v0.1.25 | normative | Runtime base: reserve / commit / release / decide / balances / events |
| [`cycles-governance-admin-v0.1.25.yaml`](cycles-governance-admin-v0.1.25.yaml) | v0.1.25 | mixed | Mostly reference admin API (runcycles' management plane; implementers MAY diverge). Eight cross-plane operations, a set of schemas, and a set of cross-plane invariants (the `WEBHOOK SUBSCRIPTION INVARIANTS`) inside this file are normative — see §MUST below. |
| [`cycles-action-kinds-v0.1.26.yaml`](cycles-action-kinds-v0.1.26.yaml) | v0.1.26 | upcoming | Action-kind registry + quota primitives. SHOULD today; MUST once v0.1.26 is the active target. |
| [`cycles-protocol-extensions-v0.1.26.yaml`](cycles-protocol-extensions-v0.1.26.yaml) | v0.1.26 | upcoming | DenyDetail, ObserveMode, v0.1.26 evaluation order, v0.1.26 schemas. SHOULD today. |
| [`cycles-governance-extensions-v0.1.26.yaml`](cycles-governance-extensions-v0.1.26.yaml) | v0.1.26 | upcoming | Policy fields for action quotas / access control; tenant observe_mode. SHOULD today. |

Operations inside v0.1.26 files still carry `x-conformance: normative` — that label describes each operation's contract *within its own spec*. Whether the spec is currently required for conformance is a separate question, answered by "current conformance target" above.

---

## MUST — required for v0.1.25 conformance

A conformant implementation MUST:

### Runtime operations (`cycles-protocol-v0.yaml`)

Implement and honor the semantics of the 4 core runtime operations:

1. `POST /v1/reservations` — **createReservation**
2. `POST /v1/reservations/{reservation_id}/commit` — **commitReservation**
3. `POST /v1/reservations/{reservation_id}/release` — **releaseReservation**
4. `POST /v1/reservations/{reservation_id}/extend` — **extendReservation** (TTL heartbeat for long-running operations)

The other runtime endpoints marked OPTIONAL / nice-to-have in `cycles-protocol-v0.yaml` (`decide`, `listReservations`, `getReservation`, `createEvent`) are listed under §SHOULD below. `GET /v1/balances` is also marked "nice-to-have" in the runtime spec but is re-declared as a normative cross-plane op in `cycles-governance-admin-v0.1.25.yaml` — it therefore appears under §MUST / Cross-plane operations, not §SHOULD. Where implemented, all these endpoints MUST follow the spec contract (paths, schemas, error codes) per their `x-conformance: normative` labels.

### Core invariants

- **Atomic reservation** — budget is locked across all affected scopes in one step; no partial locks.
- **Concurrency-safe enforcement** — shared budgets MUST NOT be oversubscribed under concurrent reserve calls.
- **Idempotent commit and release** — retries MUST be safe; the same action MUST NOT settle twice.
- **Unit consistency** — every reserve / commit / release / event operation MUST validate and preserve unit denomination.

### Error semantics

Return the exact HTTP status + `error` code pairs defined in `cycles-protocol-v0.yaml` §ERROR SEMANTICS — including `BUDGET_EXCEEDED` (409), `OVERDRAFT_LIMIT_EXCEEDED` (409), `IDEMPOTENCY_MISMATCH` (409), `RESERVATION_FINALIZED` (409), `RESERVATION_EXPIRED` (410), `UNIT_MISMATCH` (400), `NOT_FOUND` (404), and `DEBT_OUTSTANDING` (409). Where the deployment includes a governance plane (tenant records exist), the closed-tenant guard also applies: the persisting mutation surface — reservation create (`dry_run` absent or false) / commit / release / extend, and `POST /v1/events` (createEvent, a persisting budget debit) — MUST return `TENANT_CLOSED` (409) on a fresh (non-replay) request when the owning tenant's status is CLOSED (same-key replays of a pre-close mutation return their original stored response per the idempotency rule), while the non-persisting evaluations (`POST /v1/reservations` with `dry_run=true`, `POST /v1/decide`) MUST instead reflect the closed tenant as-if-live with `decision=DENY` and `reason_code=TENANT_CLOSED` on fresh (non-replay) evaluations — same-key replays of pre-close evaluations return the original stored response per the idempotency rule — enforced either by making tenant status observable to the runtime plane or by an equivalent centralized post-flip mutation guard (the requirement is behavioral, not architectural; see §ERROR SEMANTICS in the runtime spec). Only deployments with no governance tenant records at all are exempt. The v0.1.26 action-governance error codes (`ACTION_QUOTA_EXCEEDED`, `ACTION_KIND_NOT_ALLOWED`, `ACTION_KIND_DENIED`) are upcoming and listed under §Upcoming below.

### Authentication & tenancy

Authenticate via `X-Cycles-API-Key` header and enforce tenant isolation per `cycles-protocol-v0.yaml` §AUTH & TENANCY. How API keys are provisioned, rotated, or scoped to permissions is implementation-specific.

### Cross-plane operations, schemas, and invariants (currently in `cycles-governance-admin-v0.1.25.yaml`)

Although `cycles-governance-admin-v0.1.25.yaml` is mostly reference (the tenant / budget / policy / API-key / audit CRUD is runcycles' own shape), **eight operations, a set of schemas, and a set of cross-plane invariants in that file are normative** because they expose the protocol's event stream, webhook delivery contract, balance / auth introspection surface, and webhook-subscription security rules across planes. The eight operations each carry an explicit `x-conformance: normative` label; the cross-plane invariants (below) bind independently of any operation label.

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

Normative invariants (cross-plane — bind regardless of provisioning mechanism):

The webhook create/update **operations** in `cycles-governance-admin-v0.1.25.yaml` are `x-conformance: reference` (a server MAY replace the reference provisioning surface — see §MAY). The following are properties of a persisted webhook subscription's **stored state**, normative independent of any operation's `x-conformance` label: a conformant server MUST NOT be able to reach a violating persisted state by *any* provisioning path it exposes (reference tenant self-service or admin endpoints, admin-on-behalf-of, or a substituted mechanism). Defined in `cycles-governance-admin-v0.1.25.yaml` §WEBHOOK SUBSCRIPTION INVARIANTS (`info.description`):

- **Selector presence** — every persisted subscription MUST match at least one selector: at least one of `event_types` / `event_categories` is non-empty. A create/update that would leave both empty MUST be rejected `400 INVALID_REQUEST`. (document revision 0.1.25.39)
- **Tenant-owned selectors are tenant-accessible** — a subscription owned by a concrete tenant (`tenant_id` != `"__system__"`) MUST NOT carry admin-only event types or categories (`api_key` / `policy` / `webhook` / `system`). This is one rule spanning the tenant self-service path (document revision 0.1.25.38) and the admin write path (document revision 0.1.25.40); it holds under admin-key, admin-on-behalf-of, and tenant auth. `"__system__"`-owned (operator-owned) subscriptions are exempt. **One narrow carve-out:** the owner-triggered webhook test probe (`/test` operations) sends a synthetic `system.webhook_test` connectivity event directly to the subscription's own endpoint and is NOT governance-event delivery — a tenant-owned subscription MAY receive its own test probe without carrying `system` selectors; no real `system.*` / `api_key.*` / `policy.*` / `webhook.*` event may be delivered to it (see `cycles-governance-admin-v0.1.25.yaml` §WEBHOOK SUBSCRIPTION INVARIANTS → INVARIANT 2 SCOPE). Both halves are implemented in the reference stack (the admin-write-path half shipped in cycles-server-admin 0.1.25.51).

Both invariants are **provisioning-neutral**: every provisioning mechanism MUST prevent a violating subscription from being persisted and report an equivalent validation failure. The HTTP reference surfaces return `400 INVALID_REQUEST`; a non-HTTP provisioner (GitOps, direct store write, CLI) reports the equivalent failure in its own idiom and MUST NOT persist the subscription. See `cycles-governance-admin-v0.1.25.yaml` §WEBHOOK SUBSCRIPTION INVARIANTS → VIOLATION HANDLING.

> **Transitional**: these operations, schemas, and invariants currently live inside `cycles-governance-admin-v0.1.25.yaml`. A future revision will extract the event and webhook content (including the webhook subscription invariants) into dedicated `cycles-events-v0.yaml` and `cycles-webhooks-v0.yaml` files. The contract is normative regardless of file location.

### Reference-implementation status

The full v0.1.25 normative surface — including both halves of WEBHOOK SUBSCRIPTION INVARIANT 2 — is implemented in runcycles' reference stack. The admin-write-path half (tenant-owned category boundary on `createWebhookSubscription` / `updateWebhookSubscription`, document revision 0.1.25.40/.41) shipped in **cycles-server-admin 0.1.25.51** (with the last-mile delivery-guard in **cycles-server-events 0.1.25.23**); the tenant self-service half (0.1.25.38) and INVARIANT 1 (selector presence, 0.1.25.39) were already implemented.

---

## SHOULD — strongly recommended

A conformant implementation SHOULD:

- Emit events for budget-state changes (reservation.*, budget.*, quota.*) matching the `EventType` enum. Implementations MAY sample or filter which events they emit, but emitted events MUST follow the schema.
- Propagate `X-Cycles-Trace-Id` and W3C `traceparent` headers per `cycles-protocol-v0.yaml` §CORRELATION AND TRACING. Trace correlation is central to multi-service debugging.
- Implement `POST /v1/decide` — marked OPTIONAL in the v0 spec, but agent frameworks need soft-landing signals for graceful degradation.
- Implement `GET /v1/reservations` (**listReservations**) — marked OPTIONAL in v0; useful for reservation recovery (re-discover a lost `reservation_id` via `idempotency_key`), for identifying stuck `ACTIVE` reservations, and for time-window queries via the additive `from`/`to` (v0.1.25, revision 2026-05-21), `expires_from`/`expires_to`, and `finalized_from`/`finalized_to` (v0.1.25, revision 2026-05-22) parameters.
- Implement `GET /v1/reservations/{reservation_id}` (**getReservation**) — marked "optional, for debugging" in v0; valuable for support / monitoring of long-running reservations.
- Implement `POST /v1/events` (**createEvent**) — marked OPTIONAL in v0; the post-only accounting path for cases where pre-estimation is unavailable (bills-later providers, receipt ingestion).

> **Note on `GET /v1/balances`**: the runtime spec summary calls it "nice-to-have", but the admin spec (`cycles-governance-admin-v0.1.25.yaml`) re-declares the same path + operationId as a normative cross-plane op. The more-restrictive declaration wins: `getBalances` is therefore listed under §MUST (cross-plane operations), not here.
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
- Replace any or all of those reference portions with an alternative provisioning mechanism: OAuth/OIDC for auth, GitOps YAML for policies, internal admin console for tenants, direct DB writes for budget allocation, etc. (The reference portions only — the eight normative cross-plane operations listed under §MUST still apply, and a substituted webhook-provisioning mechanism MUST still uphold the §MUST webhook subscription invariants: no persisted subscription may violate selector-presence or the tenant-owned tenant-accessible-selectors rule.)
- Skip `audit_log` entirely. Not required by the protocol.
- Expose additional endpoints beyond those specified, as long as they use a non-`/v1` path prefix or a vendor-namespaced extension path (e.g., `/v1/x-runcycles/...`).
- Emit **CyclesEvidence**: populate the optional `cycles_evidence` ref (`CyclesEvidenceRef`) on decide / reserve / commit / release / error responses, serve `GET /v1/evidence/{id}` (`getEvidence`), and optionally publish the signer JWK Set at `GET /v1/.well-known/cycles-jwks.json` (`getEvidenceJwks`). These are additive and optional in `cycles-protocol-v0.yaml`; **emitting is not required for conformance**. The signed envelope they reference is specified normatively in the companion [`cycles-evidence-v0.2.yaml`](cycles-evidence-v0.2.yaml) — so an envelope a server **does** emit MUST conform to it (including, where the server publishes a JWK Set, the signer-key authority-resolution rules). A client that ignores `cycles_evidence` is fully conformant.

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
