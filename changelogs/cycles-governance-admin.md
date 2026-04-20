# cycles-governance-admin — Changelog

Keep-a-Changelog format. Most recent first. Each entry corresponds to an `info.version` bump in `cycles-governance-admin-v0.1.25.yaml`.

New entries are added directly to this file. See `scripts/validate_changelogs.py` for the CI check that keeps this in sync with the spec.

---

## v0.1.25.30 — 2026-04-20

- Editorial: declares `409 TENANT_CLOSED` responses on the ten
  mutating admin-plane operations that were missing it from their
  per-operation response maps, closing a gap between the normative
  `CASCADE SEMANTICS` Rule 2 prose (added in v0.1.25.29) and the
  OpenAPI response declarations that client SDKs and contract
  validators consume. Rule 2 already required these handlers to
  return 409 with `error_code=TENANT_CLOSED` on a CLOSED-owning-
  tenant mutation, but the response map didn't enumerate 409, so
  conformance tooling that validates response-status against the
  spec flagged a mismatch against reference servers that correctly
  implement the rule.

  Policy / API-key plane (2):
    * `PATCH /v1/admin/policies/{policy_id}` (updatePolicy)
    * `POST /v1/admin/api-keys`               (createApiKey)

  Webhook admin plane (4):
    * `POST   /v1/admin/webhooks`                        (createWebhookSubscription)
    * `PATCH  /v1/admin/webhooks/{subscription_id}`      (updateWebhookSubscription)
    * `DELETE /v1/admin/webhooks/{subscription_id}`      (deleteWebhookSubscription)
    * `POST   /v1/admin/webhooks/{subscription_id}/test` (testWebhookSubscription)

  Webhook tenant plane (4):
    * `POST   /v1/webhooks`                        (createTenantWebhook)
    * `PATCH  /v1/webhooks/{subscription_id}`      (updateTenantWebhook)
    * `DELETE /v1/webhooks/{subscription_id}`      (deleteTenantWebhook)
    * `POST   /v1/webhooks/{subscription_id}/test` (testTenantWebhook)

  Each entry references `ErrorResponse` and names the Rule 2
  trigger in its `description`. No schema changes, no new fields,
  no wire break — purely additive to the response catalog of
  already-normative behavior. Clients that treat 4xx as
  `ErrorResponse` (the canonical contract) see no observable
  change.

  Note: `createPolicy`, `updateApiKey`, `revokeApiKey`, and the
  budget lifecycle ops (create/update/fund/freeze/unfreeze, plus
  their bulk-action), along with `replayEvents` and
  `bulkActionWebhooks`, already enumerated `409 TENANT_CLOSED` in
  their response maps before this revision; this editorial pass
  brings the remaining ten ops to parity.

## v0.1.25.29 — 2026-04-20

- Adds a normative tenant-close cascade contract as a new
  `CASCADE SEMANTICS` section in `info.description`, plus matching
  references in `Tenant.status`, `updateTenant` STATUS TRANSITIONS,
  and `bulkActionTenants` CLOSE ACTION SEMANTICS. Closes a design
  gap surfaced by operators: a CLOSED tenant's FROZEN budgets were
  forever countable in `/admin/overview.budget_counts.frozen` with
  no user-reachable path to resolve them, so every closed tenant
  permanently inflated the dashboard's "needs attention" surface
  with un-fixable rows.

  The contract is stated as two complementary rules:

    * **Rule 1 — CLOSE CASCADE (server-issued, atomic).**
      On the `* → CLOSED` tenant transition (via updateTenant or
      bulkActionTenants), the server MUST, in the same transaction
      as the status flip, drive each owned object into its nearest
      terminal state:
        - `BudgetLedger` → `CLOSED` (stamp `closed_at`, preserve
          final balance snapshot for audit)
        - `ApiKey` → `REVOKED` (stamp `revoked_at`)
        - `Reservation` (open) → `RELEASED` (reason
          `tenant_closed`; no overage debt recorded)
        - `WebhookSubscription` → `DISABLED` (re-enable blocked by
          Rule 2 for closed-owner rows, making `DISABLED`
          effectively-terminal without a new enum value)

      Ordering MUST be (1) drain open reservations, (2) close
      budgets, (3) disable webhooks and revoke API keys in any
      order, (4) flip tenant.status last. Any step failure rolls
      back the whole transaction. Re-issuing close on an
      already-CLOSED tenant is a no-op.

      One audit entry per mutated owned object MUST be emitted
      under the same `correlation_id` as the originating
      `tenant.closed` entry, with reserved `event_kind` values:
        - `budget.closed_via_tenant_cascade`
        - `webhook.disabled_via_tenant_cascade`
        - `api_key.revoked_via_tenant_cascade`
        - `reservation.released_via_tenant_cascade`

    * **Rule 2 — TERMINAL-OWNER MUTATION GUARD.**
      Every mutating admin-plane operation on an owned object whose
      parent tenant is `CLOSED` MUST reject with HTTP 409 and
      `error_code=TENANT_CLOSED`. Covers freeze/unfreeze/fund/update
      on budgets, reservation lifecycle ops, API key lifecycle ops,
      all webhook lifecycle ops, and tenant-scoped policy writes.
      GET endpoints remain available (post-mortem audit read).
      Provides defense-in-depth against cascade race windows and
      stale client state; makes `WebhookSubscription.DISABLED`
      effectively-terminal for closed-owner rows without widening
      the enum.

  No wire break: no new status enum values on any owned object, no
  new `ErrorCode` values (`TENANT_CLOSED` was already declared at
  v0.1.25.x; this revision documents its normative scope). New
  audit `event_kind` strings are additive per the existing
  open-enum audit contract.

  Net operator effect once implemented: the server aggregate
  `budget_counts.frozen` drops closed-tenant owners automatically
  (their status is now `CLOSED`, not `FROZEN`), so the dashboard's
  "Frozen budgets" axis stops surfacing un-fixable rows without
  client-side filtering.

  Out of scope (parked for follow-up slices): re-opening a CLOSED
  tenant; a one-shot migration to cascade historically-orphaned
  children of pre-existing CLOSED tenants; extension-plane
  cascade for action-kinds / risk-class quotas / ACLs.

## v0.1.25.28 — 2026-04-18

- Close gap from v0.1.25.27: extends cross-surface `trace_id`
  correlation onto the `WebhookDelivery` schema so operators can JOIN
  a delivery record with the event that produced it, the audit entry
  for the originating HTTP request, and sibling deliveries in the
  same fan-out. Adds three OPTIONAL properties on
  `#/components/schemas/WebhookDelivery`:
    * `trace_id` — `^[0-9a-f]{32}$`. Captured at dispatch time from the
      originating event. Populated on every delivery whose originating
      event had a `trace_id` (always true for HTTP-originated events on
      conformant v0.1.25.28+ servers). Deliveries recorded before
      server upgrade MAY lack this field; clients MUST tolerate absence.
    * `trace_flags` — `^[0-9a-f]{2}$`. The W3C Trace Context trace-flags
      byte to use when constructing the outbound `traceparent` header
      for HTTP delivery. Preserves the inbound sampling decision when
      the originating request carried a valid `traceparent`; otherwise
      the server defaults to `01` (sampled) per cycles-protocol-v0
      §CORRELATION AND TRACING.
    * `traceparent_inbound_valid` — boolean. Whether the originating
      HTTP request presented a valid W3C `traceparent`. Used by the
      outbound delivery worker to decide whether to preserve
      `trace_flags` (true) or default to `01` (false).

  Rationale: v0.1.25.27 added `trace_id` to `Event`, `AuditLogEntry`,
  and `ErrorResponse` but not to `WebhookDelivery`. The Cycles-admin
  server impl (cycles-server-admin v0.1.25.31) naturally carries these
  fields on delivery records for the cycles-server-events sidecar to
  consume when constructing outbound `traceparent` headers (per the
  webhook-delivery prose in cycles-protocol-v0). With `additionalProperties:
  false` on `WebhookDelivery`, populating those fields without the spec
  declaring them was a contract gap — this entry closes it.

  Non-breaking: three new OPTIONAL fields; old clients tolerate unknown
  response fields by HTTP contract. Spec's additive-field guarantee
  (see preamble) applies. No field removals, no type changes, no new
  required fields.

## v0.1.25.27 — 2026-04-18

- Cross-surface correlation — adds `trace_id` (W3C Trace Context-
  compatible, 32 lowercase hex characters matching
  `^[0-9a-f]{32}$`) as an OPTIONAL property on:
    * `Event` schema
    * `AuditLogEntry` schema
    * `ErrorResponse` schema

  Purpose: link an HTTP request, its audit-log entry, and all events
  emitted as side effects of that request under a single correlation
  identifier that survives across process / queue / async
  boundaries. Complements the existing `request_id` (per-HTTP-request
  grain) and `correlation_id` (event-stream cluster grain, deterministic
  hash of `(tenant_id, scope, action_kind_or_risk_class, window,
  window_key)`). Three-tier correlation model is now:
    - `request_id` — one HTTP request. Existing. Contract strengthened.
    - `trace_id` — one logical operation across N requests. NEW.
    - `correlation_id` — event-stream JOIN key. Existing. Unchanged.

- `request_id` contract strengthened on `Event` and `AuditLogEntry`:
  MUST be populated on every entry causally downstream of an HTTP
  request, INCLUDING entries emitted from queued, deferred, or
  otherwise-async work spawned by that request (worker-pool tasks,
  delayed sweeps triggered by the request, cascaded side-effects).
  MUST be propagated across thread / queue / process boundaries along
  with trace_id; loss at the request-thread boundary is non-compliant.
  Explicit grandfathering clause: entries written before server upgrade
  to v0.1.25.27 MAY lack request_id; clients MUST tolerate its absence
  on historical entries (same forward-compat contract as ErrorCode).
  MAY be absent on internal sweeper/expiry-generated entries that have
  no originating HTTP request (periodic cron-triggered budget resets,
  startup-time reconciliation).

- `listEvents` (`GET /v1/admin/events`) — adds two optional filter
  query parameters:
    * `trace_id` — exact match, `^[0-9a-f]{32}$`. Narrows to events
      belonging to a single logical operation (may span multiple
      HTTP requests, typically yields more rows than a `request_id`
      filter).
    * `request_id` — exact match. Narrows to events emitted as side
      effects of a single HTTP request (e.g., the fan-out from a
      bulk-action endpoint).
  Both AND-compose with existing filters. Additive-parameter guarantee
  — servers that don't recognize them MUST ignore without error.

- `listAuditLogs` (`GET /v1/admin/audit/logs`) — adds the same two
  optional filter query parameters (`trace_id`, `request_id`), same
  additive-parameter guarantee. Typically yields 0 or 1 row for
  `request_id` (one audit entry per authenticated request) and N rows
  for `trace_id` when an operation spans multiple requests.

- Declares `X-Cycles-Trace-Id` in `components.headers` of this
  document so OpenAPI tooling reading the admin spec in isolation
  (SDK generators, validators) sees the cross-surface correlation
  header contract. Authoritative rules live in
  cycles-protocol-v0.yaml's CORRELATION AND TRACING section.

- Adds a CORRELATION AND TRACING cross-reference paragraph at the top
  of `info.description` pointing readers to the authoritative contract
  in cycles-protocol-v0.yaml. Discoverability-only; no new normative
  content.

- Safety / auth: no changes to authn, authz, or tenant-scoping
  behavior. AdminKeyAuth remains required on listEvents /
  listAuditLogs. trace_id is not PII — it is a server-generated (or
  client-supplied-via-header) synthetic identifier. No RBAC surface
  change.

- Backward compatibility: purely additive. `trace_id` is an OPTIONAL
  property on Event / AuditLogEntry / ErrorResponse; existing clients
  that don't read it are unaffected. The new filter params are
  additive; old clients don't send them, older servers MUST ignore
  without error. The strengthened `request_id` contract includes an
  explicit grandfathering clause so historical entries without
  request_id remain conformant for read-back.

- Refs: CORRELATION AND TRACING section of cycles-protocol-v0.yaml
  (authoritative cross-surface contract, same revision).

---

## v0.1.25.26 — 2026-04-18

- Bulk budget balance-mutation endpoint:
  `POST /v1/admin/budgets/bulk-action`. Resolves
  cycles-server-admin issue #99 ("Bulk Budget Reset at Tenant or
  Parent-Scope Level"). Operators rolling over a billing period
  no longer iterate listBudgets + per-row fundBudget; they issue
  one filtered bulk request.

  Single operation-discriminated endpoint (one path, one auth /
  audit / idempotency contract). The `action` enum
  (`CREDIT | DEBIT | RESET | RESET_SPENT | REPAY_DEBT`) mirrors
  BudgetFundingRequest.operation so any per-row fundBudget
  mutation is also expressible in bulk. The action determines
  which payload fields are required; server MUST validate the
  combination before counting matches or mutating any row.

  New schemas:
    * `BudgetBulkFilter` — mirrors listBudgets query params
      (`scope_prefix`, `unit`, `status`, `over_limit`,
      `has_debt`, `utilization_min/max`, `search`). `tenant_id`
      is REQUIRED (cross-tenant safety: no all-tenant
      fan-out from a single bulk call). Cascading reset across
      a scope subtree uses `scope_prefix` — the hierarchy is
      already encoded in the scope path; no separate `cascade`
      flag is needed.
    * `BudgetBulkActionRequest` — operation-discriminated
      request envelope: `filter`, `action`, optional `amount`
      (required for all current actions), optional `spent`
      (only honoured for RESET_SPENT), optional `reason` for
      audit trail, `expected_count` safety gate, and
      `idempotency_key`.
    * `BudgetBulkActionResponse` — per-row outcome envelope
      (`succeeded[]` / `failed[]` / `skipped[]`) reusing
      `BulkActionRowOutcome` from the existing tenant /
      webhook bulk-action infrastructure.

  Safety semantics match the existing tenant / webhook
  bulk-action contract: 500-row hard cap (HTTP 400
  LIMIT_EXCEEDED), `expected_count` preflight (HTTP 409
  COUNT_MISMATCH with no writes on drift), 15-minute
  `idempotency_key` replay window. HTTP 200 even when some
  rows fail; the per-row envelope reports per-ledger
  succeeded / failed / skipped counts. Common per-row failure
  codes: BUDGET_EXCEEDED (DEBIT would take remaining
  negative), INVALID_TRANSITION (unit mismatch, ledger
  CLOSED).

  Audit log: one AuditLogEntry per invocation (not per row),
  actor_type=ADMIN_ON_BEHALF_OF, embedding the full per-row
  outcome so security review can reconstruct exactly what
  changed.

  Authorization: AdminKeyAuth only. Tenants cannot bulk-mutate
  their own budgets via this endpoint; the per-budget mutation
  surface (fundBudget) remains unchanged.

  Backward compatible: purely additive (one new path, three
  new schemas). No existing endpoint or schema changes. No
  new top-level ErrorCode enum values: BUDGET_EXCEEDED and
  LIMIT_EXCEEDED are the request-level codes referenced by
  this endpoint, and both are already present (COUNT_MISMATCH
  and LIMIT_EXCEEDED landed in v0.1.25.23). INVALID_TRANSITION
  is a per-row outcome in BulkActionRowOutcome.error_code
  (not an ErrorResponse ErrorCode), and the row-level
  known-codes list has been extended with BUDGET_EXCEEDED so
  clients can switch on it without treating it as
  INTERNAL_ERROR.
  semantic_base unchanged at 0.1.25.9.

---

## v0.1.25.25 — 2026-04-17

- Audit tenant_id sentinel split. `AuditLogEntry.tenant_id` is
  required on every entry, but "authenticated as the platform
  admin" is semantically distinct from "failed pre-auth". The
  prior revision used a single sentinel (`<unauthenticated>`)
  for both, which made dashboards conflate admin-plane
  governance failures with anonymous attack traffic.

  This revision documents TWO sentinels on AuditLogEntry.tenant_id:
    * `__admin__` — request authenticated with a valid
      AdminKeyAuth credential but is not scoped to any single
      tenant (governance ops, cross-tenant reads, admin-plane
      failures). Retained at the authenticated-tier TTL because
      admin actions are high-signal security events.
    * `__unauth__` — request failed pre-auth (missing/invalid
      tenant key, missing admin key, path-traversal rejection,
      etc.). Retained at the unauthenticated-tier TTL and
      subject to the DDoS-sampling gate.

  Both sentinels use double-underscore delimiters (no URL
  encoding needed in filter queries: `?tenant_id=__admin__`).
  The tenant grammar `^[a-z0-9-]+$` excludes underscores, so
  collision with a real tenant id is impossible.

  Queryability preserved: tenant_id filter predicate is exact-
  match as before. Dashboards surfacing admin-plane activity
  query `?tenant_id=__admin__`; failed-attempt streams query
  `?tenant_id=__unauth__`.

  Backward compatible wire shape: AuditLogEntry.tenant_id
  remains a required string; only the documented set of
  sentinel values changes. Clients MUST treat unrecognised
  tenant_id values as opaque strings (same forward-compat
  contract as ErrorCode). No schema or required-ness changes.
  semantic_base unchanged at 0.1.25.9.

---

## v0.1.25.24 — 2026-04-17

- Audit log filter DSL upgrade on GET /v1/admin/audit/logs. Ops
  auditors cannot slice the audit trail the way their real work
  demands today: `error_code` is unfilterable, `operation` and
  `resource_type` accept only exact match, there is no status
  range, and `search` misses the two fields auditors most want
  to grep (error codes and operation IDs). This release lands
  a consistent filter DSL on the filterable fields: the
  promoted string filters (`operation`, `resource_type`,
  `error_code`, `error_code_exclude`) are exact-or-IN-list,
  and the `status` filter is exact-or-range. Filters AND-
  compose; within one filter an IN-list is OR. Out of scope
  (remain exact-match this revision): `tenant_id`, `key_id`,
  `resource_id` — see the NOT-promoted note below.

- New query parameters on listAuditLogs (all optional,
  additive-parameter guarantee: servers that don't recognise
  them MUST ignore without error):
    * error_code: array<string>, maxItems 25, explode=false.
      Exact-or-IN-list on AuditLogEntry.error_code. Case-
      sensitive. Unknown codes match nothing (forward-compat:
      a newer client sending a newly-added enum value MUST NOT
      cause a 400 against an older server). NULL entry
      error_code (success entries) MUST NOT match — auditor
      asking "show me code X" never wants success rows.
    * error_code_exclude: array<string>, maxItems 25,
      explode=false. NOT-IN-list on AuditLogEntry.error_code.
      NULL entry error_code MUST always pass — hiding noisy
      codes MUST NOT silently hide successes. MAY combine with
      error_code (AND-composed: "narrow to set A, minus subset
      B").
    * status_min: integer, 100..599. Inclusive lower bound.
      MUST be mutually exclusive with exact `status` (server
      MUST 400 on the combination). NULL entry status MUST NOT
      silently pass the range predicate.
    * status_max: integer, 100..599. Inclusive upper bound.
      Mutex with exact `status`. Server MUST 400 when
      status_min > status_max.

- Existing listAuditLogs parameters promoted from scalar to
  array. Formal wire contract is the OpenAPI `explode=false`
  comma-separated form (`?p=a,b`); a single scalar `?p=a`
  still parses into a one-element list, so older clients
  sending a scalar continue to work byte-identically. Servers
  MAY additionally accept the repeated form (`?p=a&p=b`) as
  an implementation convenience, but the repeated form is
  NOT part of the formal contract and clients MUST NOT rely
  on it for portability across servers:
    * operation: string → array<string>, maxItems 25,
      explode=false.
    * resource_type: string → array<string>, maxItems 25,
      explode=false.

- listAuditLogs `search` match set extended. Previously
  matched resource_id OR log_id. Now also matches error_code
  OR operation (case-insensitive substring, unchanged 128-
  char cap). Closes the free-text-lookup gap where
  `?search=budget` missed BUDGET_EXCEEDED and createBudget.

- NOT promoted (scope discipline): tenant_id, key_id
  (natural keys with cursor-stability implications);
  resource_id (high-cardinality, IN-list has little auditor
  value). These remain exact-match.

- Validation rules enforced at the controller edge (all
  return HTTP 400 `INVALID_REQUEST`, uniform with existing
  enum/cursor validation):
    * Each IN-list array parameter post-normalisation (trim
      each element, split commas, drop empties, dedupe)
      exceeding 25 values.
    * status exact combined with status_min OR status_max.
    * status_min or status_max outside [100, 599].
    * status_min > status_max.

- Cursor stability: implementations MUST apply all filter
  and search predicates BEFORE cursor commitment, so a
  second page with the same filter set returns the strict
  suffix of the first. Same invariant v0.1.25.21 locked in
  for `search`; this release extends it to the new IN-list
  and range predicates.

- Backward compatible: purely additive. No existing request
  or response schema modified; no field semantics changed.
  Existing single-scalar `operation` / `resource_type`
  query strings continue to work byte-identically.
  semantic_base unchanged at 0.1.25.9.

---

## v0.1.25.23 — 2026-04-17

- Enum-consistency fix for bulk-action error codes. Added
  `COUNT_MISMATCH` and `LIMIT_EXCEEDED` to the `ErrorCode` enum
  so they can appear on the wire inside `ErrorResponse.error`.
  The v0.1.25.21 prose for bulkActionTenants and
  bulkActionWebhooks already REQUIRES these codes (409 on
  expected_count mismatch, 400 on >500-row match), but the
  ErrorCode enum didn't list them — response validators running
  against the spec would reject a spec-compliant server. Purely
  additive enum widening; no required-ness change, no breaking
  change. Clients MUST already handle unknown error codes
  gracefully (the enum was always extensible for forward
  compatibility), so this is observability-safe.

---

## v0.1.25.22 — 2026-04-17

- Editorial-only cleanup across the spec family. No wire changes,
  no schema changes, no required-ness changes, no enum changes.
  Prose-only rewrites to remove implementation-version markers
  from normative prose and replace them with behavior-based
  wording, per the AUTHORING CONVENTION documented in this file.
- Affected prose in this file:
  * SortDirection schema description — dropped "introduced in
    v0.1.25.20" marker; keeps the additive-parameter guarantee
    wording.
  * BudgetLedger.tenant_id description — reworded
    "pre-v0.1.25.19 server responses" to behavior-based
    "older server responses that may omit the field."
  * EventDataReservationDenied.deny_detail description — replaced
    "v0.1.26 servers populate this with DenyDetail fields" with
    "Servers implementing the governance action-quotas extension
    populate this with DenyDetail fields."
  * listBudgets.sort_by description — removed "(unchanged from
    pre-v0.1.25.20 behavior)" parenthetical.
  * bulkActionTenants and bulkActionWebhooks endpoint
    descriptions — removed "Added in v0.1.25.21" markers; the
    CHANGELOG still records their introduction.
- Affected prose in companion specs (merged artifact
  regeneration captures these):
  * cycles-governance-extensions-v0.1.26.yaml — replaced five
    "v0.1.26 servers MUST..." clauses with "Servers implementing
    this extension MUST..." Rewrote "Existing tenants
    (pre-v0.1.26)" as "Tenants created before this extension
    was adopted."
  * cycles-protocol-extensions-v0.1.26.yaml — replaced "Ignored
    by v0.1.25 servers" with behavior-based "Servers that do
    not implement this extension MUST ignore the field without
    error." Rewrote the comment-block "v0.1.26 servers populate
    the base fields directly" as "Servers implementing this
    extension populate the base fields directly."
  * cycles-spec-index.yaml denied_event_population note — same
    treatment.
- Rationale: the spec is a protocol contract, not a changelog
  of server binaries. Impl-version markers in normative prose
  conflate what a specific version did with what the contract
  requires. Reviewers flagged this as the one remaining
  consistency gap after PR #49.
- Merged artifacts regenerated; spectral lint clean (0 errors
  across 5 source specs and 2 merged artifacts); merge-drift
  check passes.

---

## v0.1.25.21 — 2026-04-17

- Free-text search on admin list endpoints. New optional
  `search` query parameter on the six admin list endpoints
  (listTenants, listBudgets, listApiKeys, listAuditLogs,
  listWebhookSubscriptions, listEvents). Case-insensitive
  substring match; maxLength 128; empty string MUST be treated
  as absent; combines with other filter params using AND.
  Per-endpoint match fields:
    * listTenants: tenant_id, name.
    * listBudgets: tenant_id, scope.
    * listApiKeys: key_id, name.
    * listAuditLogs: resource_id, log_id.
    * listWebhookSubscriptions: subscription_id, url.
    * listEvents: correlation_id, scope.
  Closes the dashboard-side workflow gap where "find tenant
  matching 'acme'" required client-side filtering over a
  truncated page-1 slice of the full list (silent false
  negatives at scale). Purely additive; servers that don't
  recognize `search` MUST ignore it.

- Filter-driven bulk lifecycle actions for tenants and webhook
  subscriptions. Two new endpoints:
    * POST /v1/admin/tenants/bulk-action
      (SUSPEND | REACTIVATE | CLOSE)
    * POST /v1/admin/webhooks/bulk-action
      (PAUSE | RESUME | DELETE)
  Both take { filter, action, expected_count, idempotency_key }
  where `filter` mirrors the corresponding list endpoint's
  query params (tenant_id, status, search, etc.), letting
  operators preview the target set via GET with the same
  filter before submitting the mutation.

  Safety primitives:
    * expected_count: server counts matches BEFORE any writes;
      mismatch returns HTTP 409 COUNT_MISMATCH and performs no
      writes (anti-footgun gate protecting against filter
      drift between preview and submit).
    * idempotency_key: 15-minute replay window; repeat submits
      with the same key return the original response without
      re-applying the action.
    * HARD LIMIT: 500 matching rows per invocation; larger
      filters return HTTP 400 LIMIT_EXCEEDED, forcing operators
      to narrow the filter. Bounds worst-case transaction size
      and keeps the request synchronous.
    * Per-row failures land in `failed[]`; per-row no-ops land
      in `skipped[]`. Overall HTTP 200 even with partial
      failure — callers inspect the response envelope for
      success/failure counts.

  Replaces the client-side N-sequential-PATCH pattern (which
  produced partial-failure modes, thundering-herd request
  bursts, and no idempotency on retry) with a single
  server-owned transaction.

- New schemas: BulkActionRowOutcome, TenantBulkFilter,
  TenantBulkActionRequest, TenantBulkActionResponse,
  WebhookBulkFilter, WebhookBulkActionRequest,
  WebhookBulkActionResponse.

- Backward compatible: purely additive. No existing request
  or response schema modified; no field semantics changed.
  semantic_base unchanged at 0.1.25.9.

---

## v0.1.25.20 — 2026-04-16

- Server-side sort for admin list endpoints. Closes the
  silent-wrong-answer hazard where a client-side sort applied
  over a cursor-paginated response only orders the loaded
  slice. Under cursor pagination, the server's cursor order
  determines what appears on page N+1. A UI that advertised
  "sort by utilization desc" while the server paginated by
  created_at could hide the highest-utilization rows on a
  later page and never surface them, even though the UI
  claimed to be sorted. This is the same class of defect that
  v0.1.25.18 closed for cross-tenant filters.

- New optional query parameters on the six admin list
  endpoints (listTenants, listApiKeys, listBudgets,
  listWebhookSubscriptions, listEvents, listAuditLogs):
    * sort_by: string — per-endpoint enum. See each endpoint
      for the allowed values.
    * sort_dir: "asc" | "desc" — default "desc".
  When sort_by is provided, the server MUST return results in
  the requested order and MUST encode the sort key into the
  opaque cursor so subsequent page fetches continue in sort
  order. When omitted, the server MUST use its previous
  default ordering (wire behavior is unchanged for clients
  that never send these params).

- Per-endpoint sort_by enums (cross-checked against dashboard
  column surfaces):
    * listTenants: tenant_id, name, status, created_at.
      Default: created_at.
    * listApiKeys: key_id, name, tenant_id, status,
      created_at, expires_at. Default: created_at.
    * listBudgets: tenant_id, scope, unit, status,
      commit_overage_policy, utilization, debt.
      Default: utilization. Utilization is computed as
      spent / allocated consistent with the
      utilization_min / utilization_max filter semantics
      (allocated == 0 is treated as utilization == 0).
      commit_overage_policy is sorted by lexicographic enum
      order.
    * listWebhookSubscriptions: url, tenant_id, status,
      consecutive_failures. Default: consecutive_failures.
    * listEvents: event_type, category, scope, tenant_id,
      timestamp. Default: timestamp.
    * listAuditLogs: timestamp, operation, resource_type,
      tenant_id, key_id, status. Default: timestamp.

- Servers MUST reject sort_by values outside the endpoint's
  allowed enum with HTTP 400. Servers MUST reject sort_dir
  values outside {asc, desc} with HTTP 400. These 400 causes
  are covered by the existing "Malformed cursor / limit /
  enum value" 400 response on each endpoint — no new response
  code is introduced.

- Older admin servers that don't recognize sort_by / sort_dir
  MUST ignore them without error (additive-parameter
  guarantee). Clients that require deterministic sort order
  SHOULD detect absent-server-sort behavior via known-server-
  version gating (cycles-spec-index.yaml base_governance >=
  0.1.25.20) rather than inferring support from response
  content.

- Cursor interaction: cursors returned by servers that
  received a sort_by parameter are only valid for continued
  pagination under the same (sort_by, sort_dir, filters)
  tuple. Sending a cursor from one sort under a different
  sort_by or sort_dir produces undefined ordering (or HTTP
  400 — either is spec-compliant). Clients MUST reset the
  cursor when changing sort key or direction.

- Backward compatible: purely additive. Existing callers that
  never sent sort_by / sort_dir observe no behavior change —
  the server's previous default ordering remains the default.
  No request or response schema changes.
  semantic_base unchanged at 0.1.25.9.

---

## v0.1.25.17 — 2026-04-15

- Added RESET_SPENT operation to BudgetFundingRequest.operation
  enum. Closes a long-standing gap between the docs (which have
  always described RESET as "for period rollovers, plan changes")
  and the RESET implementation (which only resizes the allocated
  ceiling and preserves spent — a strict no-op on an exhausted
  budget when called with the same allocated amount).

  RESET_SPENT sets allocated to the given amount AND sets spent
  to the optional `spent` field (defaults to 0), while preserving
  reserved (active runtime reservations straddle the period
  boundary and will land in the new period's spent when they
  commit) and debt (period boundaries don't forgive debt —
  REPAY_DEBT remains the explicit channel for that).

  The optional `spent` parameter supports four legitimate
  operator needs beyond routine period rollovers:
    * migration from another billing system (import a customer
      with their existing consumption already reflected)
    * prorated mid-period signup (new customer starts partway
      through a period)
    * credit-back / compensation (reduce spent after an
      incident)
    * state correction (fix a miscounted spent after upstream
      bugs)
  Constrained to >= 0. Resulting `remaining` is allowed to go
  negative if the supplied `spent` plus `reserved` and `debt`
  exceed `allocated` — matches existing overdraft ledger
  semantics.

- Added `budget.reset_spent` event type to the event enum
  (distinct from `budget.reset`). Event consumers can now
  distinguish routine billing-period boundaries from resize
  operations in dashboards, webhook handlers, and compliance
  queries.

- Extended `EventDataBudgetLifecycle`:
    * `operation` enum gains RESET_SPENT.
    * `previous_state` and `new_state` nested objects gain
      optional `spent` and `reserved` fields so pre/post
      snapshots carry those values across the event.
    * New optional `spent_override_provided` boolean field
      (only populated on budget.reset_spent) flags whether
      the spent value was explicitly supplied (migration/
      correction use cases, which need compliance scrutiny) or
      defaulted to 0 (routine rollover).

- Extended `BudgetFundingResponse` with optional
  `previous_spent` and `new_spent` fields. Populated when spent
  changes (RESET_SPENT); for preserve-spent operations,
  previous_spent == new_spent when both are emitted so callers
  can verify no-op-on-spent visually.

- Existing RESET semantics are UNCHANGED. The RESET description
  in the operation enum and in the POST /v1/admin/budgets/fund
  endpoint prose has been clarified to say "Resize the allocated
  ceiling" (accurate) rather than "Use for period rollovers"
  (which misdirected operators to RESET when they should have
  used the now-distinct RESET_SPENT).

- Backward compatibility: additive. New fields are optional;
  new enum values are additive (consumers MUST ignore
  unrecognised enum values per the spec's existing
  extensibility policy). Clients still sending RESET get the
  same behaviour as before.

---

## v0.1.25.19 — 2026-04-16

- BudgetLedger gains an optional tenant_id property. Closes a
  companion gap to v0.1.25.18: once listBudgets allows omitting
  tenant_id under AdminKeyAuth, the response becomes cross-tenant
  but each returned BudgetLedger still has no wire-level way to
  tell callers which tenant owns it. Parsing tenant_id from the
  scope string is possible in practice but not guaranteed by
  this spec (scope formats are opaque). Exposing tenant_id
  explicitly lets cross-tenant dashboards render per-row tenant
  context without scope-string parsing.
- tenant_id is defined as OPTIONAL on the response schema rather
  than required. Rationale: mixed-fleet deployments. Admin
  servers implementing v0.1.25.18 or earlier never populate the
  field; marking it required would fail OpenAPI-strict response
  validators against those older servers. Servers implementing
  v0.1.25.19+ MUST populate tenant_id on every BudgetLedger they
  return (from any endpoint — getBudget, listBudgets, createBudget,
  etc.). Clients that need tenant context MAY assume the field
  is present when talking to v0.1.25.19+ servers and SHOULD fall
  back to scope-string heuristics (or refuse to display) when
  absent.
- Under ApiKeyAuth, tenant_id on the response always equals the
  authenticated tenant; clients that already know this from
  context may ignore the field. Under AdminKeyAuth, the field
  is load-bearing — it's how cross-tenant callers attribute a
  ledger to its tenant.
- Backward compatible: additive response field. No request
  schema change. Existing clients that ignore unknown response
  fields observe no change. Clients that fail on unknown fields
  (unusual) would already have been failing on the v0.1.25.18
  listBudgets cross-tenant shape and are out of scope for
  compatibility here.
  semantic_base unchanged at 0.1.25.9.

---

## v0.1.25.18 — 2026-04-16

- Cross-tenant admin list endpoints: relax required-tenant_id
  constraint on GET /v1/admin/api-keys and GET /v1/admin/budgets
  when AdminKeyAuth is used. Closes dashboard N+1 storm (one
  listApiKeys call per tenant on every poll, one listBudgets
  call per tenant for "over-limit" filter) and closes the silent
  cross-tenant miss where a client-side filter applied after a
  per-tenant page-1 fetch would drop matches on page 2+.
    * listApiKeys: tenant_id is now OPTIONAL under AdminKeyAuth
      (returns keys across all tenants, cursor-paginated).
      Under ApiKeyAuth the parameter remains ignored — the
      authenticated tenant is always used for scoping (unchanged).
      Admin callers that pass tenant_id see no behavior change
      (explicit tenant filter still applies).
    * listBudgets: tenant_id is now OPTIONAL under AdminKeyAuth
      (returns budgets across all tenants, cursor-paginated,
      composable with the new filter params below). Under
      ApiKeyAuth the parameter is still ignored — authenticated
      tenant scoping applies (unchanged). Admin callers that
      pass tenant_id see no behavior change.
- New additive filter query params on listBudgets (supported
  under both ApiKeyAuth and AdminKeyAuth; under ApiKeyAuth the
  filters apply within the authenticated tenant's scope):
    * over_limit: boolean — when true, returns only budgets where
      the budget's overdraft_limit has been breached (is_over_limit
      is true on the returned ledger). When false, returns only
      budgets NOT over limit. Absent = no filter.
    * has_debt: boolean — when true, returns only budgets with
      debt > 0. When false, returns only budgets with debt == 0.
      Absent = no filter.
    * utilization_min: number [0..1] — inclusive lower bound on
      budget utilization (spent / allocated). Budgets with
      allocated == 0 are treated as utilization == 0 for this
      filter. Absent = no lower bound.
    * utilization_max: number [0..1] — inclusive upper bound on
      budget utilization. Budgets with allocated == 0 are treated
      as utilization == 0. Absent = no upper bound.
  Servers MUST combine all filter params with AND semantics and
  MUST apply them BEFORE cursor-based pagination (so cursor
  traversal is stable under a filter).
- Rationale: before this revision, admin dashboards operating
  at 1k+ tenants had no wire-level way to ask a cross-tenant
  question ("which budgets are over limit across the fleet?",
  "list all API keys"). The only available shape was
  per-tenant iteration, which is O(tenants) sequential HTTP
  calls per poll and silently misses matches beyond page 1
  for client-side filters.
- Backward compatible: purely additive + constraint relaxation.
    * Existing admin callers that always pass tenant_id observe
      no behavior change.
    * Existing admin callers that always pass the OpenAPI-valid
      subset of params observe no behavior change (new params
      are optional).
    * ApiKeyAuth callers observe no behavior change — tenant
      scoping is still derived from the authenticated key.
    * 400 response on listBudgets changes meaning: it no longer
      fires for "missing tenant_id under AdminKeyAuth". It still
      fires for malformed cursor / limit / enum values. Spec
      response schema unchanged.
  semantic_base unchanged at 0.1.25.9.

---

## v0.1.25.16 — 2026-04-14

- Editorial cleanup. Removed implementation-version markers from
  normative prose. A protocol spec describes a contract; it does
  not describe what a specific server binary happened to do at a
  specific version. ~35 substantive edits across this file,
  cycles-governance-extensions-v0.1.26.yaml, and
  cycles-protocol-extensions-v0.1.26.yaml.
- Three edit classes:
    * Server-binary references rewritten as implementation-neutral
      contract language. E.g. "Keys created before v0.1.25.6..."
      became "Servers MAY encounter legacy API keys with explicit
      permission sets..."; "ignored by v0.1.25.7 servers" became
      "Servers that don't recognize this parameter MUST ignore it".
    * Editorial provenance markers inline with clauses (e.g.
      "WILDCARD SEMANTICS (v0.1.25.7):", "Added in v0.1.25.15.",
      "Optional manage flag (v0.1.25.13+)") dropped or replaced
      with normative qualifiers. The feature-origin information
      is preserved in the CHANGELOG entries that introduced each
      clause; duplicating it inline with the prose creates
      drift-prone coupling to server version history.
    * Endpoint-description markers ("AUTH (v0.1.25.15+):",
      "Under AdminKeyAuth (v0.1.25.14):" repeated on six webhook
      endpoints) dropped. The security block + operation prose
      describes authoritative behavior independent of spec
      revision.
- New authoring convention added to this file's top-of-spec
  doc-string. Future reviewers can point at it when rejecting
  the same class of drift in new PRs.
- Kind A references retained unchanged:
    * CHANGELOG section headers ("v0.1.25.15 (2026-04-14):")
    * Cross-references between changelog entries
    * Filename references ("cycles-governance-admin-v0.1.25.yaml")
    * semantic_base values (0.1.25.9) — the frozen wire identity
    * Explicit forward-migration timelines
      ("fallback removed in v0.1.27")
- Backward compatible: purely editorial. No schema, endpoint,
  field meaning, or error code changed. semantic_base unchanged
  at 0.1.25.9.

---

## v0.1.25.15 — 2026-04-14

- Dual-auth (ApiKeyAuth | AdminKeyAuth) added to GET /v1/auth/introspect.
  Matches the pattern established by v0.1.25.13 (budgets/policies),
  the 2026-04-13 reservations revision in cycles-protocol-v0, and
  v0.1.25.14 (webhooks). Existing admin callers see no behavioral
  change.
- Under ApiKeyAuth, AuthIntrospectResponse gains three additive
  fields — all populated only when auth_type=tenant:
    * tenant_id (REQUIRED under tenant auth): the tenant the key
      is bound to. MUST be absent when auth_type=admin.
    * scope_filter (OPTIONAL): non-empty when the key has scope
      restrictions; absent or empty means no scope narrowing.
    * auth_type enum gains value "tenant" alongside existing "admin".
- NORMATIVE capability-derivation rules added to the Capabilities
  schema description: servers MUST derive the capabilities map
  from a tenant key's permissions set per the published table.
  Guarantees predictable capability output from permission input
  across servers and clients; prevents independent implementations
  from drifting into subtly different rule sets.
- Rationale: forward-compatibility stake for multi-role clients
  (tenants signing in to the admin dashboard, SDK-embedded
  dashboards, etc.). No server implementation required in this
  spec revision — servers continue returning admin-only introspect
  until they explicitly extend to ApiKeyAuth. The spec defines
  what compliant servers MUST return when they do.
- Explicit non-goals (deferred to future revisions):
    * No tenant-scoped Overview endpoint (/v1/admin/overview stays
      admin-only).
    * No tenant-scoped Audit query (/v1/admin/audit/logs stays
      admin-only).
    * No admin-on-behalf-of introspect of a specific tenant key.
- Backward compatible: purely additive. No existing schema,
  endpoint, field meaning, or error code changed. Clients built
  against v0.1.25.14 continue to parse v0.1.25.15 responses
  correctly under admin auth.

---

## v0.1.25.14 — 2026-04-13

- Dual-auth (ApiKeyAuth | AdminKeyAuth) added to six tenant-scoped
  webhook endpoints so admin operators can pause / force-delete /
  diagnose tenant self-service webhooks during incident response
  without needing the tenant's API key. Matches the pattern
  established by v0.1.25.13 (budgets/policies) and the 2026-04-13
  reservations revision in cycles-protocol-v0:
    - GET    /v1/webhooks                           (listTenantWebhooks)
    - GET    /v1/webhooks/{subscription_id}         (getTenantWebhook)
    - PATCH  /v1/webhooks/{subscription_id}         (updateTenantWebhook)
    - DELETE /v1/webhooks/{subscription_id}         (deleteTenantWebhook)
    - POST   /v1/webhooks/{subscription_id}/test    (testTenantWebhook)
    - GET    /v1/webhooks/{subscription_id}/deliveries (listTenantWebhookDeliveries)

  Motivating use case: a tenant's webhook endpoint is flapping
  (auto-disabled after consecutive failures, or spamming a shared
  downstream). Ops gets paged, needs to pause / delete / inspect
  deliveries without waiting for the tenant to rotate keys or
  provide one. Admin already owns `/v1/admin/webhooks/*` for
  admin-provisioned subscriptions; this closes the gap for
  tenant-provisioned ones.

- Intentionally NOT dual-auth (admin-on-behalf-of footgun):
    - POST /v1/webhooks  (createTenantWebhook) — URL choice, event
      subscriptions, and signing secrets are tenant policy. Admin
      creating a subscription on a tenant's behalf entangles
      provenance in a way that obscures the audit trail.
    - POST /v1/webhooks/{subscription_id}/replay — already admin-only
      at `/v1/admin/webhooks/{id}/replay`; tenant self-service replay
      remains tenant-key-only (bulk event re-delivery is a
      capacity-planning decision owed to the tenant).

- Semantic delta on listTenantWebhooks: new `tenant` query
  parameter. REQUIRED when called with AdminKeyAuth (admin has no
  effective tenant, can't otherwise scope the listing); same
  single-param dual-semantic pattern as listBudgets / listPolicies
  / listReservations. MUST NOT be set when using ApiKeyAuth
  (tenant is implicit from the key). Omitting `tenant` under
  AdminKeyAuth MUST return 400 INVALID_REQUEST with message
  "tenant query parameter is required when using admin key
  authentication".

- Tenant-scoping (NORMATIVE) on the per-subscription endpoints
  (GET / PATCH / DELETE / POST test / GET deliveries): admin
  callers do not pass `tenant` — the owning tenant is resolved
  from the subscription record. If the subscription does not
  exist, the server MUST return 404 (not 403 — 404 is the
  existing ApiKeyAuth behavior, preserved for consistency with
  tenant-scoped callers who also see 404 on cross-tenant reads).

- Audit-log requirement (NORMATIVE): admin-driven calls to these
  endpoints MUST record actor_type=admin_on_behalf_of in the
  shared audit store so the governance audit-query surface
  (GET /v1/admin/audit/logs) returns them alongside other
  admin-on-behalf-of actions. Callers SHOULD populate an optional
  `reason` field where one exists in the request body (PATCH,
  DELETE) with a structured prefix like `[WEBHOOK_PAUSE]` for
  grep-ability. No schema change needed — existing WebhookUpdateRequest
  already permits additional operator metadata via the
  (already-optional) `metadata` property; `reason` is best-effort
  additional context server-side.

- Backward compatibility: purely additive. Existing ApiKeyAuth
  callers see no behavior change. The new `tenant` query parameter
  on listTenantWebhooks is validation-only under ApiKeyAuth and
  MAY be omitted (unchanged from today). No schemas modified.

---

## v0.1.25.13 — 2026-04-13

- Dual-auth (ApiKeyAuth | AdminKeyAuth) added to three previously
  tenant-only write endpoints so admin operators can provision
  budgets and policies on behalf of tenants from the dashboard:
    - POST   /v1/admin/budgets   (createBudget)
    - POST   /v1/admin/policies  (createPolicy)
    - PATCH  /v1/admin/policies/{policy_id}  (updatePolicy)

  Matches the existing dual-auth pattern on listBudgets / listPolicies
  (read) and POST /v1/admin/budgets/fund (write). The dashboard
  previously had no path to create budgets/policies — only freeze /
  unfreeze / fund / update were exposed — because it authenticates
  exclusively with X-Admin-API-Key.

- Schema additions for admin-on-behalf-of routing:
    - BudgetCreateRequest gains optional `tenant_id` (string).
    - PolicyCreateRequest gains optional `tenant_id` (string).
  Required when the call uses AdminKeyAuth (server needs to know
  which tenant owns the new resource); MUST NOT be set when using
  ApiKeyAuth (tenant is implicit from the key, server rejects with
  400 INVALID_REQUEST if both present).

- updatePolicy needs no body change — `policy_id` in the path
  already pins the owning tenant; the server validates that the
  policy resolves before applying the update.

- Audit-log requirement: admin-key-driven calls to these endpoints
  MUST record actor_type=ADMIN_ON_BEHALF_OF so security review can
  distinguish admin-driven creates from tenant self-service. (Audit
  schema unchanged — actor_type is already present and now gets a
  new enum value the server emits.)

- Backward compatibility: purely additive. Existing ApiKeyAuth
  callers see no change. Tenant-key request bodies that previously
  omitted tenant_id continue to work and are still spec-conformant.

---

## v0.1.25.12 — 2026-04-12

- Targeted error-response documentation for admin operations
  that emit 404 / 409 but didn't document them. Follows up on
  v0.1.25.11's 400 sweep. Unblocks strict response-status
  validation in the admin server — it had to keep
  'validation.response.status.unknown' as IGNORE in the
  contract validator because these specific statuses weren't
  documented.

- Added '404 Not Found' on PATCH /v1/admin/tenants/{tenant_id}.
  The server correctly returns 404 when the target tenant
  doesn't exist; the spec was silent. GET and DELETE on this
  path already had 404; only PATCH was missing it.

- Added '409 Conflict' on POST /v1/admin/policies. Server
  returns 409 DUPLICATE_RESOURCE when a policy with the same
  name already exists for a tenant.

- Added '409 Conflict' on DELETE /v1/admin/api-keys/{key_id}.
  Server returns 409 when the key is already revoked
  (ALREADY_REVOKED). The operation is idempotent-friendly but
  the conflict path is real and now documented.

- No semantic changes. Purely additive: any previously-valid
  response is still valid. Clients that strictly-validate
  responses will now accept documented-and-conformant 404/409
  ErrorResponse bodies on these paths.

---

## v0.1.25.11 — 2026-04-12

- Completeness fix for error-response documentation. Adds '400'
  (Bad request) response entry to all 28 operations that lacked
  one, referencing the existing ErrorResponse schema. Server has
  always returned 400 on malformed JSON / missing required
  fields / invalid enum values; the spec was silent. All 43
  operations now document 400.
- Unblocks strict response-status validation in downstream
  contract testing — previously the admin server's
  ContractValidationConfig had to IGNORE
  'validation.response.status.unknown' because the spec didn't
  document 400 responses. That escape hatch can now be removed.
- No semantic changes to responses already documented. Purely
  additive. Clients that strictly-validate responses against
  this spec will now accept a documented-and-conformant 400
  ErrorResponse where before they would have rejected it as an
  unknown status.

---

## v0.1.25.10 — 2026-04-12

- Contract-test hardening uncovered by full schema audit against the
  admin server. Four fixes, all non-breaking for conformant clients.

- NEW SignedAmount schema, ported from cycles-protocol-v0.yaml (which
  has carried it since v0. The admin spec was missing it entirely.)
  Like Amount but without the minimum:0 floor, so fields that can
  legitimately go negative in overdraft/debt scenarios validate
  correctly. References updated for:
    * BudgetLedger.remaining (was Amount)
    * BudgetFundingResponse.previous_remaining (was Amount)
    * BudgetFundingResponse.new_remaining (was Amount)
  Reason: v0.1.25 explicitly documents debt/overdraft producing
  negative remaining (BudgetLedger description, debt semantics).
  The prior Amount reference with minimum:0 contradicted that
  feature and broke strict response validators.

- NEW BalanceListResponse schema + $ref swap on GET /v1/balances.
  Was BudgetListResponse (wrapper field: ledgers). Now the wrapper
  field is 'balances', consistent with cycles-protocol-v0 /v1/balances
  BalanceResponse wrapper. Per design principle "admin should be
  consistent with runtime protocol where doing the same thing": the
  admin-plane balance query is functionally equivalent to the
  runtime-plane query (same endpoint path, same semantic), so it
  uses the same wrapper field name. Item type remains BudgetLedger
  (admin plane exposes richer per-ledger fields than runtime Balance).

- Added 'additionalProperties: false' to three inline PATCH request
  bodies that were missing it, restoring consistency with the rest of
  the spec's strict-properties policy:
    * PATCH /v1/admin/tenants/{tenant_id} (TenantUpdateRequest inline)
    * PATCH /v1/admin/budgets (BudgetUpdateRequest inline)
    * PATCH /v1/admin/policies/{policy_id} (PolicyUpdateRequest inline)
  PATCH /v1/admin/api-keys/{key_id} already had it; PATCH webhook
  endpoints use named schemas that already had it.

---

## v0.1.25.9 — 2026-04-12

- Error response completeness for SDK codegen and client error handling.
  All changes are additive and backward compatible with v0.1.25.8.
- Added '500' (Internal server error) response to all 45 endpoints.
  Previously undocumented; documents existing server behavior.
- Added '403' (Forbidden) response to 29 endpoints that lacked it.
  AdminKeyAuth endpoints use generic "Forbidden" description;
  ApiKeyAuth endpoints (commitReservation, getBalances) use
  permission-specific descriptions. The 16 ApiKeyAuth endpoints
  that already had '403' are unchanged.
- No schema changes, no new endpoints, no new required fields.

---

## v0.1.25.8 — 2026-04-10

- Dashboard and observability hardening for v0.1.26 readiness.
  All changes are additive and backward compatible with v0.1.25.7.
- EventDataReservationDenied extensibility:
  * reason_code enum changed from closed to open (string with
    known values documented). Servers MAY emit extension reason
    codes; strict validators that previously rejected unknown
    values now accept them.
  * Added optional policy_id field — identifies which policy
    caused the denial when applicable. Backfills a long-standing
    dashboard gap (could not filter denials by policy).
  * Added optional deny_detail field (generic object) for
    operator-grade context. Extensions (e.g., v0.1.26) populate
    this with structured detail like quota_violation,
    blocked_by_policy, blocked_by_scope, suggested_fix.
- AdminOverviewResponse dashboard enrichments (all optional):
  * tenant_counts.in_observe_mode — count of tenants in shadow
    mode (requires v0.1.26 observe_mode extension to populate).
  * quota_health — aggregate counter health summary (counts at/
    near limit, top offenders). Populated by v0.1.26 servers.
  * recent_denials_by_reason — denial count breakdown by
    reason_code over the event window.
  * access_control_stats — count of policies with allow/deny
    lists configured.
- Query parameter additions (additive, ignored by v0.1.25.7 servers):
  * listTenants: observe_mode filter (requires v0.1.26 extension).
  * listPolicies: has_action_quotas and references_action_kind
    filters (require v0.1.26 extension).
- Backward compatibility: All v0.1.25.7 clients and servers
  continue to work unchanged. New optional fields are absent
  in responses from v0.1.25.7 servers. New query parameters
  are ignored by v0.1.25.7 servers.
- Relationship to v0.1.26 extensions:
  * The v0.1.26 governance extension no longer needs to declare
    EventDataReservationDeniedExtension; it uses the now-open
    base schema directly.
  * The v0.1.26 governance extension's AdminOverviewResponse
    guidance is now codified in the base as optional fields.

---

## v0.1.25 — 2026-03-31

- Added Pillar 4: Events & Webhooks (Observability Plane).
- Added 29 new schemas:
    * Core event model: EventCategory, EventType (40 types across 6 categories), Event.
    * Event data payloads (13 schemas): EventDataBudgetLifecycle, EventDataBudgetThreshold,
      EventDataBudgetOverLimit, EventDataBudgetDebtIncurred, EventDataBurnRateAnomaly,
      EventDataReservationDenied, EventDataReservationExpired, EventDataRateSpike,
      EventDataCommitOverage, EventDataTenantLifecycle, EventDataApiKey, EventDataPolicy,
      EventDataSystem.
    * Webhook management (13 schemas): WebhookSubscription, WebhookThresholdConfig,
      WebhookRetryPolicy, WebhookCreateRequest, WebhookCreateResponse, WebhookUpdateRequest,
      WebhookListResponse, WebhookDelivery, WebhookDeliveryListResponse, WebhookTestResponse,
      EventListResponse.
    * Missing schemas from v0.1.24 (2): ReservationTtlOverride, RateLimits (were referenced
      by PATCH /v1/admin/policies/{policy_id} but never defined).
- Added 7 new paths (10 operations):
    * POST   /v1/admin/webhooks — Create webhook subscription
    * GET    /v1/admin/webhooks — List webhook subscriptions
    * GET    /v1/admin/webhooks/{subscription_id} — Get subscription details
    * PATCH  /v1/admin/webhooks/{subscription_id} — Update subscription
    * DELETE /v1/admin/webhooks/{subscription_id} — Delete subscription
    * POST   /v1/admin/webhooks/{subscription_id}/test — Send test event
    * GET    /v1/admin/webhooks/{subscription_id}/deliveries — List delivery attempts
    * GET    /v1/admin/events — Query event stream
    * GET    /v1/admin/events/{event_id} — Get single event
    * POST   /v1/admin/webhooks/{subscription_id}/replay — Replay historical events
- Added 40 event types across 6 categories:
    * budget (15): created, updated, funded, debited, reset, debt_repaid, frozen, unfrozen,
      closed, threshold_crossed, exhausted, over_limit_entered, over_limit_exited,
      debt_incurred, burn_rate_anomaly.
    * reservation (5): denied, denial_rate_spike, expired, expiry_rate_spike, commit_overage.
    * tenant (6): created, updated, suspended, reactivated, closed, settings_changed.
    * api_key (6): created, revoked, expired, permissions_changed, auth_failed,
      auth_failure_rate_spike.
    * policy (3): created, updated, deleted.
    * system (5): store_connection_lost, store_connection_restored, high_latency,
      webhook_delivery_failed, webhook_test.
- Added 4 new ErrorCode values: WEBHOOK_NOT_FOUND, WEBHOOK_URL_INVALID, EVENT_NOT_FOUND,
  REPLAY_IN_PROGRESS.
- Added Webhooks and Events tags for Pillar 4 endpoints.
- Design decisions:
    * Implementation-agnostic naming (system.store_* not system.redis_*).
    * Extensible event types: consumers MUST ignore unrecognized types; custom.* prefix reserved.
    * Category-level wildcard subscriptions (e.g., subscribe to all budget.* including future types).
    * At-least-once delivery semantics with event_id for consumer deduplication.
    * HMAC-SHA256 payload signing via X-Cycles-Signature header.
    * Auto-disable after consecutive failures with manual re-enable via PATCH.
- Bug fixes (pre-existing in v0.1.24):
    * Added missing security block (AdminKeyAuth) to PATCH /v1/admin/budgets.
    * Fixed 3 broken $refs using #/components/responses/ErrorResponse (should be inline
      response definitions): PATCH /v1/admin/budgets 404/409, PATCH /v1/admin/policies 404.
    * Added missing ReservationTtlOverride and RateLimits schemas (referenced by
      PATCH /v1/admin/policies/{policy_id} but never defined).
- Added per-tenant webhook self-service: 8 new tenant-scoped endpoints at /v1/webhooks
  and /v1/events using ApiKeyAuth. Tenants can manage their own webhooks and query
  their own events. Restricted to budget.*, reservation.*, and tenant.* event types
  (26 of 40). Admin-only: api_key.*, policy.*, system.*.
- Added webhook endpoint IP allowlisting: WebhookSecurityConfig schema with blocked
  CIDR ranges (RFC 1918 + loopback + link-local blocked by default), allowed URL
  patterns (glob), and allow_http flag. Admin endpoint GET/PUT /v1/admin/config/webhook-security.
- Added granular admin permissions: 12 new namespaced permissions
  (admin:tenants:read/write, admin:budgets:read/write, etc.). Existing admin:read
  and admin:write retained as wildcards for backward compatibility.
- Added 3 new tenant API key permissions: webhooks:read, webhooks:write, events:read.
- Backward compatibility: All changes are purely additive. No schemas, paths, methods,
  fields, enum values, or response codes were removed. Clients built against v0.1.24
  work unchanged against v0.1.25.

---

## v0.1.25.7 — 2026-04-09

- Backward compatibility fix: admin:read and admin:write now act as wildcards
  at the server level. admin:write satisfies any *:write permission requirement
  (budgets:write, policies:write, webhooks:write). admin:read satisfies any
  *:read requirement (budgets:read, policies:read, events:read, etc.).
  This ensures pre-v0.1.25.6 keys with admin:write continue to work without
  migration. admin:read does NOT satisfy *:write.
- Added 401 responses to all 36 auth-gated endpoints that were missing them.
  Every endpoint with a security scheme now documents 401.
- Centralized FROZEN semantics in BudgetLedger.status: now explicitly states
  "no new reservations, commits, or funding operations" (was missing funding).
- Clarified webhook/event permissions are opt-in: webhooks:read, webhooks:write,
  events:read are NOT in the default tenant key permission set.
- Clarified createApiKey provisions tenant-scoped keys only. The admin key
  (X-Admin-API-Key) is server-configured, not provisioned through this endpoint.
- Added PATCH /v1/admin/api-keys/{key_id} for updating key permissions,
  scope_filter, name, description, metadata without secret rotation.
  Emits api_key.permissions_changed on permission/scope_filter changes.
  400 on invalid permission names, 409 on revoked/expired keys.
- Extracted reusable Permission enum schema. ApiKey.permissions,
  ApiKeyCreateRequest.permissions, and PATCH api-keys request body all
  reference Permission via $ref for consistent codegen and validation.
- Permission schema documents wildcard semantics (admin:read/admin:write)
  as normative — not just in changelog.
- Clarified admin permissions on tenant keys: accepted for backward
  compatibility but SHOULD NOT be assigned to new tenant keys.
- Fixed 401 description precision: admin-only endpoints say "admin API key",
  tenant-only say "API key", dual-auth say "API key / admin key".
- Fixed stale schema header comment (v0.1.25.6 → v0.1.25.7).

---

## v0.1.25.6 — 2026-04-08

- Budget freeze/unfreeze: Added dedicated action endpoints for operational
  status transitions. BudgetLedger.status already included FROZEN, events
  budget.frozen/budget.unfrozen already existed, and fund() already blocked
  on frozen budgets — but there was no API to transition status.
    * POST /v1/admin/budgets/freeze — transitions ACTIVE → FROZEN (AdminKeyAuth)
    * POST /v1/admin/budgets/unfreeze — transitions FROZEN → ACTIVE (AdminKeyAuth)
    * Query params: scope (required), unit (required)
    * Optional request body: reason, metadata
    * Responses: 200 (BudgetLedger), 400, 401, 404, 409 (invalid transition)
    * 409 cases: already frozen, already active, budget closed
- Admin fund: Extended POST /v1/admin/budgets/fund with dual-auth.
    * AdminKeyAuth now accepted as alternative security scheme.
    * When using AdminKeyAuth: tenant_id query parameter is REQUIRED.
    * When using ApiKeyAuth: existing behavior unchanged (tenant_id ignored,
      uses authenticated tenant).
    * Added 400 response for missing tenant_id with AdminKeyAuth.
    * Added 403 response for scope_filter denial (ApiKeyAuth callers).
- Added 1 new schema: BudgetStatusTransitionRequest (reason, metadata).
- Added 4 new tenant API key permissions: budgets:read, budgets:write,
  policies:read, policies:write. Budget/policy tenant endpoints now require
  explicit permissions (403 if missing), consistent with webhooks/events model.
- Added 403 responses to POST /v1/admin/budgets, POST /v1/admin/policies,
  PATCH /v1/admin/policies/{policy_id}, POST /v1/admin/budgets/fund for
  permission and scope_filter denial.
- Added 403 responses and PERMISSIONS documentation to all tenant webhook
  self-service endpoints (GET/PATCH/DELETE/POST /v1/webhooks/...) and
  GET /v1/events for permission consistency with budgets/policies.
- Freeze/unfreeze endpoint descriptions now explicitly document event emission
  (budget.frozen, budget.unfrozen).
- Updated AdminKeyAuth description to include fund in allowlist.
- Backward compatibility: All changes are purely additive. Keys created with
  default permissions include the new budget/policy permissions automatically.
  Keys created before v0.1.25.6 with explicitly specified permission sets may
  need migration if they do not include budgets:read/write or policies:read/write.
  Servers SHOULD apply fallback semantics (grant budget/policy access to pre-existing
  keys that lack explicit permission strings) or migrate persisted keys at startup.

---

## v0.1.25.5 — 2026-04-08

- Dashboard support: Added dual-auth allowlist for admin dashboard reads.
    * GET /v1/admin/budgets and GET /v1/admin/policies now accept AdminKeyAuth
      as an alternative security scheme for read access. When using AdminKeyAuth,
      the tenant_id query parameter is required for scoping (400 if missing).
    * GET /v1/admin/budgets/lookup does not require tenant_id — budget is
      uniquely identified by (scope, unit) pair.
- Added tenant_id query parameter to GET /v1/admin/policies (was missing;
  GET /v1/admin/budgets already had it).
- Added 3 new endpoints:
    * GET /v1/admin/budgets/lookup — exact single-budget retrieval by scope + unit.
    * GET /v1/admin/overview — server-aggregated operational dashboard payload
      with entity counts, top-offender arrays, and recent event summaries.
    * GET /v1/auth/introspect — returns effective capabilities for the
      authenticated credential (AdminKeyAuth only in v1).
- Added 2 new schemas: AdminOverviewResponse (strict: all fields required,
  additionalProperties: false on nested objects), AuthIntrospectResponse
  (all capability booleans required).
- Added Dashboard tag for overview and introspect endpoints.
- Added 400/401/403 error responses on all new and modified endpoints.
- Documented dual-auth allowlist semantics in AdminKeyAuth security scheme.
- Backward compatibility: All changes are purely additive. Existing ApiKeyAuth
  callers are unaffected.

---

## v0.1.24 — 2026-03-24

- Initial release of the Complete Budget Governance System API.
- Three integrated pillars: Tenant & Budget Management, Authentication &
  Authorization, Runtime Enforcement.
- 25 schemas, 13 paths, 19 operations.
- Aligned with Cycles Protocol v0.1.24 for runtime enforcement schemas.
- Tenant lifecycle (ACTIVE/SUSPENDED/CLOSED), budget ledgers with overdraft,
  policy-based caps and rate limits, API key provisioning with permissions,
  audit logging, cursor-based pagination.
