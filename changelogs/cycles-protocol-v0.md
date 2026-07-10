# cycles-protocol-v0 — Changelog

Keep-a-Changelog format. Most recent first. Each entry corresponds to an `info.version` bump in `cycles-protocol-v0.yaml`.

New entries are added directly to this file. See `scripts/validate_changelogs.py` for the CI check that keeps this in sync with the spec.

---

## v0.1.25.13 — 2026-07-10

_(revision 2026-07-10 — TENANT_CLOSED on the runtime ErrorCode enum + closed-tenant mutation binding)_

- **`TENANT_CLOSED` added to the ErrorCode enum** for HTTP 409 rejections of
  reservation mutations whose owning tenant is CLOSED; mirrors the governance
  spec's code of the same name (its CASCADE SEMANTICS Rule 2 terminal-owner
  mutation guard, added there in v0.1.25.29, scopes "any reservation
  create/commit/release/extend" — but the runtime enum never carried the
  code, so a conformant runtime-plane 409 body was impossible to construct).
- **ERROR SEMANTICS closed-tenant binding (NORMATIVE).** `POST
  /v1/reservations` (create), commit, release, and extend MUST return HTTP
  409 with error=TENANT_CLOSED when the owning tenant's status is CLOSED and
  the CLOSED flip is durable. Rationale: the close cascade revokes the
  tenant's API keys, so closed tenants usually surface on the runtime plane
  as 401 UNAUTHORIZED — but governance Mode B invariant (a) requires that a
  mutation observed after the flip MUST NOT succeed even in the window
  before keys are revoked; this binding closes that race on the runtime
  plane. Precedence: for non-replay mutations, TENANT_CLOSED takes
  precedence over the reservation-state errors (RESERVATION_FINALIZED,
  RESERVATION_EXPIRED) per Rule 2's "regardless of that child's own
  current status"; idempotent same-key replays of pre-close mutations
  retain replay precedence and return the original stored response
  (consistent with Rule 2 invariant (b)). Applicability: a deployment
  that operates a governance plane MUST enforce the guard — by making
  CLOSED status observable to the runtime plane, or via an equivalent
  centralized post-flip mutation guard; the requirement is behavioral,
  not architectural. Only deployments with no governance tenant records
  at all are exempt. Non-mutating reservation reads (GET
  /v1/reservations, GET /v1/reservations/{id}) are never rejected with
  TENANT_CLOSED (mirrors Rule 2's read-access rule). The extendReservation
  operation's local ERROR SEMANTICS list gains the matching bullet.
- **Dry-run / decide closed-tenant rule (NORMATIVE).** The 409 binding is
  scoped to the PERSISTING mutation surface (create with `dry_run` absent
  or false, commit, release, extend). Non-persisting evaluations — `POST
  /v1/reservations` with `dry_run=true` and `POST /v1/decide` — MUST NOT
  return 409 TENANT_CLOSED; a fresh (non-replay) evaluation MUST
  reflect the closed tenant as-if-live with decision=DENY and
  reason_code=TENANT_CLOSED (TENANT_CLOSED added to DecisionReasonCode's
  documented known values).
  Rationale: dry-run/decide outcomes are attestations of what live
  execution would do and MAY be captured as signed evidence
  (cycles-evidence-v0.2.yaml); an evaluation that ignores a durable
  CLOSED flip would attest ALLOW for a request whose live execution MUST
  fail. Guard evaluation on both surfaces: a malformed tenant record
  (status undeterminable) fails closed with 500 INTERNAL_ERROR — the
  server cannot attest against corrupt governance state; an absent
  tenant record is unguarded. Same-key replays of pre-close evaluations
  return the original stored response per the IDEMPOTENCY rules — replay
  precedence applies on the non-persisting surface exactly as on the
  persisting one. The createReservation DRY-RUN RESPONSE RULES and the
  /decide operation description carry matching local blocks.
- Additive only (one enum value; otherwise prose) — semantic_base remains 0.1.25.

## v0.1.25.12 — 2026-07-04

_(revision 2026-07-04 — clarify webhook per-tenant ordering under retries + actor.type prose parity)_

- **WEBHOOK EVENT GUIDANCE ordering (clarification).** The delivery-protocol
  bullet promised "events for the same tenant are dispatched in order"
  without addressing retries — but any per-delivery retry-with-backoff
  scheme (which the same section mandates) necessarily re-queues a failed
  delivery behind later events. Now explicit: the ordering guarantee covers
  FIRST delivery attempts only; retried deliveries MAY arrive after later
  same-tenant events; consumers MUST NOT assume strict arrival ordering
  across retry boundaries and should reconstruct order from the envelope
  `timestamp` / `correlation_id`, not arrival order. Codifies what every
  conformant implementation (including the reference dispatcher) already
  does; surfaced as a spec ambiguity by the 2026-07-03 events-server audit.
- **Standard event payload actor prose**: actor.type value list now includes
  `admin_on_behalf_of`, mirroring the governance spec's Event.actor.type
  enum (added there in v0.1.25.36).
- **`LIMIT_EXCEEDED` added to the ErrorCode enum** for HTTP 429 throttling
  responses (the SHOULD-level rate limiting on the public getEvidence /
  getEvidenceJwks endpoints). The runtime enum previously had no
  throttling code, so a conformant 429 ErrorResponse body was impossible
  to construct; mirrors the governance spec's code of the same name (used
  there for its 429s since v0.1.25.23). ERROR SEMANTICS now states the
  429 → LIMIT_EXCEEDED binding.
- Additive only (one enum value; otherwise prose) — semantic_base remains 0.1.25.

## v0.1.25.11 — 2026-07-03

_(revision 2026-07-03 — resolve two long-standing ambiguities: getReservation EXPIRED semantics and Subject standard-field charset)_

- **getReservation EXPIRY (NORMATIVE clarification).** The ERROR SEMANTICS 410
  rule previously enumerated only the mutation endpoints
  (commit/release/extend), while the GET operation declared a 410 response
  without saying when it fires — implementations had flip-flopped between
  `200 status=EXPIRED` and `410`. Now explicit: `GET /v1/reservations/{id}`
  MUST return 410 RESERVATION_EXPIRED for a reservation whose status is
  EXPIRED (404 only for never-existed); EXPIRED rows remain visible as normal
  200 rows on `listReservations`. Codifies the reference implementation's
  settled behavior (cycles-server AUDIT Issue 10). The 410 response now
  carries its own description + headers instead of the bare ErrorResponse ref.
- **Subject CHARSET (NORMATIVE clarification).** Standard subject fields
  carried only `maxLength: 128`, leaving unstated whether servers may reject
  characters that collide with the canonical scope encoding (":" and "/" are
  structural delimiters). Now explicit: values SHOULD match
  `^[a-zA-Z0-9_.-]+$`; servers MAY reject out-of-pattern values with 400
  INVALID_REQUEST (the reference implementation does); portable clients
  SHOULD stay within the pattern. Deliberately prose (MAY/SHOULD), not a
  schema `pattern:` constraint — tightening the schema would be a breaking
  wire change for permissive servers under the evolution contract.
- No schema, field, or wire change — description text and one response-object
  expansion only; semantic_base remains 0.1.25.

## v0.1.25.10 — 2026-06-24

_(revision 2026-06-24 — re-point CyclesEvidence cross-references to the promoted normative spec)_

- Editorial only: updates the in-spec references to the CyclesEvidence
  envelope draft from `drafts/cycles-evidence-v0.1.yaml` to the promoted
  normative spec `cycles-evidence-v0.2.yaml` (on `CyclesEvidenceRef`,
  `getEvidence`, `getEvidenceJwks`, and the response-mirror notes). The
  envelope wire shape and the `cycles_evidence` surface are unchanged; the
  `schema_version` discriminator the runtime references stays
  `cycles-evidence/v0.1`. No schema, field, or wire change — semantic_base
  remains 0.1.25.

## v0.1.25.9 — 2026-06-22

_(revision 2026-06-22 — link reservations to their evidence envelopes)_

- Adds the optional `evidence` field to `ReservationSummary` and
  `ReservationDetail`: a `ReservationEvidence` map keyed by artifact type
  (`reserve` / `commit` / `release`) whose values are `CyclesEvidenceRef`s.
  Lets a consumer jump from a reservation straight to its signed envelope(s)
  via `getEvidence` without having captured the `evidence_id` off the original
  reserve/commit/release response (runcycles/cycles-dashboard follow-up).
- Adds the `ReservationEvidence` component schema.
- Adds the `evidence` token to the `listReservations` `include` projection.
  Like `metadata` / `committed_metadata` it is OMITTED FROM LIST ROWS BY
  DEFAULT and projected only when the caller opts in (`?include=evidence`);
  it is PROJECTION-ONLY and MUST NOT participate in cursor / filter-hash
  binding. On the single-row `ReservationDetail` it is always present (when
  the reservation has recorded evidence).
- `evidence` is TRANSPORT METADATA, NOT ATTESTED (see `CyclesEvidenceRef`):
  each entry is recorded after its artifact's `evidence_id` was computed.
  Absent when evidence emission is disabled or for reservations that predate
  evidence support.
- Additive + non-breaking: an optional property on existing response schemas
  and an additive, ignore-if-unrecognized projection token. Clients that don't
  read it, and servers that don't populate it or honor `include=evidence`, are
  unaffected.

## v0.1.25.8 — 2026-06-19

_(revision 2026-06-19 — surface `committed` + opt-in metadata on `listReservations`)_

- Adds `committed`, `metadata`, and `committed_metadata` to
  `ReservationSummary` (the `GET /v1/reservations` list rows), closing the
  inconsistency where these fields surfaced on the single-row
  `ReservationDetail` but were dropped from list responses
  (runcycles/cycles-server#201, follow-up to #197).
- `committed` (the COMMIT charge, a small scalar) is returned
  UNCONDITIONALLY on COMMITTED list rows — on the same footing as
  `finalized_at_ms`.
- `metadata` (RESERVE-time) and `committed_metadata` (COMMIT-time) are
  arbitrary-size, possibly-PII maps, so they are OMITTED FROM LIST ROWS BY
  DEFAULT and projected only when the caller opts in via a new
  `include` query parameter (`?include=metadata,committed_metadata`).
- Adds the `include` query parameter to `listReservations`: a
  comma-separated field-projection list. Unrecognized/empty tokens are
  ignored without error; it is PROJECTION-ONLY and MUST NOT participate in
  cursor / filter-hash binding (changing `include` mid-pagination does not
  invalidate a cursor), distinguishing it from the window filters.
- Additive + non-breaking: optional properties on an existing response
  schema and an additive, ignore-if-unrecognized query parameter. Clients
  that don't read the new fields, and servers that don't populate them or
  honor `include`, are unaffected.

## v0.1.25.7 — 2026-06-18

_(revision 2026-06-18 — expose commit-time metadata on `getReservation`)_

- Adds the optional `committed_metadata` field to `ReservationDetail` (the
  `GET /v1/reservations/{reservation_id}` response). It carries the metadata
  supplied on the COMMIT request (`CommitRequest.metadata`), preserved on the
  reservation record and surfaced on read — previously a server could accept and
  store commit metadata but had no field to return it, so it was effectively
  write-only (runcycles/cycles-server#197). Also clarifies the existing
  `metadata` field as RESERVE-time metadata, distinct from `committed_metadata`.
  Additive + non-breaking: an optional property on an existing response schema;
  clients that don't read it are unaffected, and servers that don't populate it
  simply omit it.

## v0.1.25.6 — 2026-06-15

_(revision 2026-06-15 — publish the signer JWK Set: `getEvidenceJwks`)_

- Adds the public endpoint `GET /v1/.well-known/cycles-jwks.json`
  (`getEvidenceJwks`, `security: []`) and the `CyclesEvidenceJwks` /
  `CyclesEvidenceJwk` schemas — the publication half of the ADDITIVE
  signer-key-resolution layer (cycles-evidence v0.2). It lets a consumer resolve
  a `did:cycles` `signer_did` (or confirm a raw-hex one) to a public key and
  establish signer AUTHORITY, not merely signature validity. The resolvable
  `signer_did` form, the NORMATIVE validity-window key selection, the
  deterministic-selection rules, and the verification dispositions live in
  `drafts/cycles-evidence-v0.1.yaml` (`CyclesEvidenceJwks`); these schemas mirror
  the required shape for the serving endpoint, exactly as `CyclesEvidenceEnvelope`
  mirrors the envelope for `getEvidence`. Located API-base-relative
  (`{server_id}/.well-known/cycles-jwks.json`, where `server_id` already carries
  `/v1`), deliberately NOT origin-rooted, so key authority stays anchored to the
  base the `did:cycles` hash commits to. PUBLIC because a JWK Set is public keys
  only (the private signing key is never served); the set is itself the trust
  anchor consumers resolve. OPTIONAL to publish — a server not doing signer-key
  resolution returns 404 and consumers fall back to raw-hex `signer_did` +
  `expected_signer` pinning. Additive + non-breaking.

## v0.1.25.5 — 2026-06-13

_(revision 2026-06-13 — surface `cycles_evidence` on the error response)_

- Adds the optional `cycles_evidence` field (`CyclesEvidenceRef`) to
  `ErrorResponse`, closing the last gap in the lifecycle binding loop
  (decide / reserve / commit / release / **error**). The `error` artifact wraps
  any 4xx/5xx `ErrorResponse` from the four core runtime endpoints and is the
  canonical home for non-dry reserve denials — insufficient budget surfaces as
  HTTP 409 `BUDGET_EXCEEDED`, NOT a 200 with `decision: DENY` (see
  §ReservationCreateResponse.decision) — which the evidence draft calls the
  highest-signal evidence an APS receipt can bind to. Surfacing the ref in-band
  lets a denied caller bind its own signed receipt to the denial and fetch the
  envelope via `getEvidence`. The field is `CyclesEvidenceRef`, identical in
  shape/semantics to the four success responses; it is TRANSPORT METADATA, NOT
  attested (the `error` artifact's `payload.error.response` mirror in
  `drafts/cycles-evidence-v0.1.yaml` keeps `additionalProperties: false` and
  omits it, so the content hash is never self-referential). Present when the
  server emitted an `error` envelope for this response; absent when emission is
  disabled or for errors raised before evidence could be emitted (e.g. request
  validation / auth failures). Additive + non-breaking.

---

## v0.1.25.4 — 2026-06-13

_(revision 2026-06-13 — surface `cycles_evidence` on the decide response)_

- Adds the optional `cycles_evidence` field (`CyclesEvidenceRef`) to
  `DecisionResponse`, completing the lifecycle binding loop (decide / reserve /
  commit / release). The `decide` artifact attests a pre-execution decision
  (ALLOW / ALLOW_WITH_CAPS / DENY); it is already modelled in
  `drafts/cycles-evidence-v0.1.yaml` (`DecidePayload` = `{request, response}`, no
  reservation created) with golden fixtures `01-decide-allow` /
  `09-decide-risk-points-allow`. Forbidden/validation failures on `/v1/decide`
  are NOT `decide` evidence — they surface as 4xx in the `error`-artifact DOMAIN
  (the verifier-domain fixture `12-decide-live-forbidden` illustrates that shape;
  the reference server itself omits `cycles_evidence` for such pre-evaluation
  auth/validation failures — see the error artifact's domain-vs-emission note in
  `drafts/cycles-evidence-v0.1.yaml`). Present unless emission is disabled;
  additive + non-breaking.

---

## v0.1.25.3 — 2026-06-13

_(revision 2026-06-13 — surface `cycles_evidence` on commit + release responses)_

- Adds the optional `cycles_evidence` field (`CyclesEvidenceRef`) to
  `CommitResponse` and `ReleaseResponse`, extending the reserve binding loop
  (v0.1.25.1) to the rest of the budget lifecycle. The `commit` artifact attests
  the actual spend and the `release` artifact the returned reservation — both
  already modelled in `drafts/cycles-evidence-v0.1.yaml` (`CommitPayload` /
  `ReleasePayload`, golden fixtures `05/06/07/13`). Present unless evidence
  emission is disabled; same synchronous-id / async-sign semantics as reserve.
  Additive + non-breaking per the EVOLUTION CONTRACT.

---

## v0.1.25.2 — 2026-06-12

_(revision 2026-06-12 — clarify `cycles_evidence` non-attestation + fix the url join)_

- **`cycles_evidence_url` join fix**: `server_id` is already the canonical base
  URL *including* `/v1` (e.g. `https://cycles.example.com/v1`), so the URL is
  `{server_id}/evidence/{evidence_id}` — NOT `{server_id}/v1/evidence/...` (which
  double-prefixed `/v1`). Documented normatively on the field.
- **Non-attestation of `cycles_evidence`**: stated explicitly that the ref is
  transport metadata, NOT part of the attested payload. The `evidence_id` is
  computed over the pre-evidence-ref response; the `ReservationCreateResponseMirror`
  in `drafts/cycles-evidence-v0.1.yaml` keeps `additionalProperties: false` and
  omits `cycles_evidence` so the content hash is never self-referential. Servers
  MUST compute `evidence_id` before stamping the ref onto the wire response.

---

## v0.1.25.1 — 2026-06-12

_(revision 2026-06-12 — surface `cycles_evidence` on the reserve response)_

- Adds `CyclesEvidenceRef` (`{evidence_id, cycles_evidence_url}`) and an
  optional `cycles_evidence` field on `ReservationCreateResponse`. The
  `evidence_id` (sha256 content hash of the JCS-canonical envelope) is computed
  SYNCHRONOUSLY at decision time and returned on the reserve response, even
  though the envelope is Ed25519-signed and stored ASYNCHRONOUSLY. This closes
  the binding loop: a caller (e.g. an APS gateway) records `evidence_id` on its
  own signed receipt and resolves the envelope via `getEvidence` at
  `cycles_evidence_url`. Present on both ALLOW and DENY; absent only when
  emission is disabled. Because sign/store is async, `getEvidence` MAY return a
  transient `404` immediately after the response — consumers SHOULD retry.

---

## v0.1.25 — 2026-06-12

_(revision 2026-06-12 — public `getEvidence` envelope retrieval endpoint)_

- Adds `getEvidence` (`GET /v1/evidence/{evidence_id}`): fetch a signed
  CyclesEvidence envelope by its sha256 content id. PUBLIC (no `ApiKeyAuth`)
  — the unguessable `evidence_id` is a capability, and the envelope is
  content-addressed + Ed25519-signed, so any receipt holder (e.g. an APS
  gateway or auditor) can fetch and verify it offline. Servers SHOULD
  rate-limit and serve it immutably-cacheable. `404` on unknown id.
- Records the public exception in the top-level `AUTH & TENANCY` prose (which
  otherwise states all requests authenticate via `X-Cycles-API-Key`), and
  defines the public-endpoint response contract: `429` (with `Retry-After` /
  `X-RateLimit-Reset`) and a `Cache-Control` response header on `200`.
- Adds the `CyclesEvidenceEnvelope` response schema (mirrors the required
  shape; the normative definition remains `drafts/cycles-evidence-v0.1.yaml`)
  and the `EvidenceId` path parameter.
- Resolves the serving-surface question deferred in `cycles-evidence-v0.1`
  (which left it "implementation-defined"): the retrieval endpoint is now
  specced, and `cycles_evidence_url` derives by convention as
  `{server_id}/evidence/{evidence_id}`.

## v0.1.25 — 2026-05-22

_(revision 2026-05-22 — `expires_*` / `finalized_*` time-range filters on listReservations)_

- Adds four optional query parameters to `listReservations`
  (`GET /v1/reservations`), mirroring the shape of the
  `from`/`to` window filter shipped in revision 2026-05-21:
    * `expires_from`: ISO 8601 date-time. Inclusive lower bound
      on `expires_at_ms`. May be supplied alone (open upper bound)
      or paired with `expires_to`.
    * `expires_to`: ISO 8601 date-time. Inclusive upper bound on
      `expires_at_ms`. May be supplied alone (open lower bound)
      or paired with `expires_from`.
    * `finalized_from`: ISO 8601 date-time. Inclusive lower bound
      on `finalized_at_ms`.
    * `finalized_to`: ISO 8601 date-time. Inclusive upper bound
      on `finalized_at_ms`.
- Closes the use case left out of the 2026-05-21 revision: cleanup
  sweepers that need to locate reservations expiring (or already
  expired/finalized) within a window. The original `from`/`to`
  binds to `created_at_ms`, which is unhelpful for "find what's
  expiring in the next hour" or "find all rows finalized today".
- All three windows compose with AND semantics. A row must satisfy
  every supplied window predicate to be returned. Each pair is
  independently bound to its target field — `expires_*` binds to
  `expires_at_ms` regardless of `sort_by` (just like `from`/`to`
  binds to `created_at_ms`), and `finalized_*` likewise.
- `finalized_at_ms` is OPTIONAL on `ReservationSummary` /
  `ReservationDetail` and is populated ONLY on COMMITTED and
  RELEASED rows (absent on ACTIVE and EXPIRED). Rows where the
  field is absent MUST be excluded from results when either
  `finalized_from` or `finalized_to` is supplied — the predicate
  naturally fails on field-absent rows; making the exclusion
  normative ensures all conformant servers agree on the behavior.
  Callers who want a window over EXPIRED rows should use
  `expires_from` / `expires_to` against `expires_at_ms`, which
  is required on every row.
- `finalized_at_ms` added as an OPTIONAL property to
  `ReservationSummary`. Pre-revision the field was declared only
  on `ReservationDetail` while `ReservationSummary` carried
  `additionalProperties: false` — meaning servers could not
  legally include it in list results, and the proposed filter
  would have produced rows whose timestamps callers could not
  see without a follow-up `getReservation` call. The summary now
  carries the same field with the same population semantics as
  the detail; existing clients with strict schemas remain
  compatible because the field is OPTIONAL (absent in pre-revision
  responses, valid under the new schema when present).
- Validation (mirrors revision 2026-05-21):
    * Servers MUST reject `expires_from > expires_to` and
      `finalized_from > finalized_to` with HTTP 400
      INVALID_REQUEST.
    * Either side of each pair may be supplied alone.
    * Malformed date-time values MUST be rejected with HTTP 400
      INVALID_REQUEST.
    * Blank-string values for any window bound MUST be treated
      as unset (NORMATIVE; applies to all six bounds — `from`,
      `to`, `expires_from`, `expires_to`, `finalized_from`,
      `finalized_to`). A client sending `?expires_from=` MUST
      be handled identically to one omitting the param. This
      makes normative the behavior the cycles-server reference
      implementation has shipped since v0.1.25.20 (the original
      `from`/`to` revision) — strict implementers would
      otherwise reasonably 400 on `""` per the `format: date-time`
      declaration, and divergence between conformant servers on
      this common client-side pattern (`?from=${maybeUnset}`)
      is the kind of cryptic-400 the additive-parameter
      guarantee is designed to avoid.
- Additive-parameter guarantee: servers that don't recognize the
  new parameters MUST ignore them without error and return the
  unfiltered set. Older clients that never send them get the
  pre-revision wire behavior byte-for-byte.
- Cursor invalidation extends the v0.1.25.20 `FilterHasher` shape:
  sorted-path cursors fold all six window-bound values into the
  canonical filter hash, so reusing a sorted cursor under a
  different `(from, to, expires_from, expires_to, finalized_from,
  finalized_to)` tuple returns HTTP 400 INVALID_REQUEST. Legacy
  Redis-SCAN cursors do not carry filter state and are not
  window-validated (matching how the legacy path already treats
  every other filter).
- TIME-RANGE FILTERS prose block in the listReservations
  operation description rewritten to cover all three field
  bindings (`from`/`to` on `created_at_ms`, `expires_*` on
  `expires_at_ms`, `finalized_*` on `finalized_at_ms`) and the
  AND-composition rule.
- Backward compatible: purely additive. Four new query parameters
  on `listReservations`; one new OPTIONAL property
  (`finalized_at_ms`) on `ReservationSummary` mirroring the same
  field already on `ReservationDetail`. No request-body schema
  changes. Old clients ignore the new query params and tolerate
  the new response field (absent on pre-revision servers). Both
  ApiKeyAuth and AdminKeyAuth callers see the new parameters.

---

## v0.1.25 — 2026-05-21

_(revision 2026-05-21 — `from`/`to` created-time range filters on listReservations)_

- Adds two optional query parameters to `listReservations`
  (`GET /v1/reservations`):
    * `from`: ISO 8601 date-time. Inclusive lower bound on
      reservation `created_at_ms`. May be supplied alone (no
      upper bound) or paired with `to`.
    * `to`: ISO 8601 date-time. Inclusive upper bound on
      reservation `created_at_ms`. May be supplied alone (no
      lower bound) or paired with `from`.
- Closes a real client-side cost: today, fetching "last 24h
  of reservations" requires sort-by-`created_at_ms` + a
  page-size escalation loop until the oldest item falls
  outside the window. For high-volume agent clusters this
  scans far more rows than the caller actually needs. With
  `from`/`to`, the server boundaries the scan to the
  requested window and pagination over that window remains
  cursor-stable.
- Both parameters bind to `created_at_ms` regardless of
  `sort_by`. A client sorting by `expires_at_ms` while
  filtering by `from`/`to` gets the expected behavior:
  results in the requested window, ordered by expiry. This
  keeps the contract predictable across sort keys (no
  per-key filter semantics to memorize).
- Validation:
    * Servers MUST reject `from > to` with HTTP 400
      INVALID_REQUEST.
    * Either parameter alone is valid; absent parameter
      means "no bound on that side."
    * Malformed date-time values MUST be rejected with HTTP
      400 INVALID_REQUEST (consistent with other ISO 8601
      query parameters in the spec family).
- Additive-parameter guarantee: servers that don't recognize
  `from`/`to` MUST ignore without error and return the
  unfiltered set. Older clients that never send them get the
  pre-revision wire behavior byte-for-byte.
- Naming and wire-type rationale: matches the family-wide
  `from`/`to` + `format: date-time` convention already in
  use on `listAuditLogs`, `listEvents`,
  `listWebhookDeliveries`, `listTenantEvents`, and
  `listTenantWebhookDeliveries` in the governance-admin
  spec. Bespoke `created_after`/`created_before` names or
  Unix-epoch wire types would split the convention for
  clients and codegen.
- Backward compatible: purely additive. No request or
  response schema changes. Both ApiKeyAuth and AdminKeyAuth
  callers see the new parameters.

---

## v0.1.25 — 2026-04-18

_(revision 2026-04-18 — trace_id cross-surface correlation, W3C Trace Context-compatible)_

- Adds a cross-plane CORRELATION AND TRACING normative section to
  `info.description`. The section is binding for every Cycles server
  operation on every plane (runtime, governance-admin, action-kinds,
  and all extensions that layer onto these bases). Companion specs
  carry a brief cross-reference to this section and do not restate a
  conflicting contract. Contract summary:
    * Three-tier correlation model: `request_id` (per-HTTP-request),
      `trace_id` (per logical operation), `correlation_id` (event-stream
      cluster grain). `trace_id` is new; the other two already existed.
    * Inbound header precedence: `traceparent` (valid W3C Trace Context)
      > `X-Cycles-Trace-Id` (valid 32-hex) > server-generates. Malformed
      headers fall through silently; servers MUST NOT reject for a
      malformed correlation header. If both headers are present, valid,
      and disagree, `traceparent` wins.
    * Server-generated trace_id: 16 random bytes encoded as 32 lowercase
      hex characters. All-zero value is invalid per W3C Trace Context
      §3.2.2.3 and MUST be re-rolled.
    * Outbound response: every response on every plane (2xx, 4xx, 5xx)
      MUST echo the `X-Cycles-Trace-Id` header. ErrorResponse bodies
      MUST carry `trace_id`.
    * Propagation: trace_id travels from the inbound request onto the
      audit-log entry, every event emitted as a side effect, and every
      outbound webhook delivery (as both `X-Cycles-Trace-Id` header and
      `trace_id` event-body field). Propagation across thread / queue
      / process boundaries is REQUIRED.

- Adds `X-Cycles-Trace-Id` to `components.headers` and references it
  from every response that currently references `X-Request-Id` (both
  `components.responses.ErrorResponse` and all inline response-header
  blocks in `paths`).

- Adds `trace_id` as an OPTIONAL property to `ErrorResponse`. Pattern
  `^[0-9a-f]{32}$`. The `additionalProperties: false` constraint on
  `ErrorResponse` is preserved — `trace_id` is a DECLARED property, not
  an undeclared extra, so strict validators accept it.

- Webhook delivery prose updated to require two additional outbound
  headers on every delivery:
    * `X-Cycles-Trace-Id: {trace_id}` — always present.
    * `traceparent: 00-{trace_id}-{fresh-span-id-16-hex}-{trace-flags}` —
      W3C Trace Context version 00. trace_id matches X-Cycles-Trace-Id.
      span-id is freshly generated per outbound delivery (NOT reused
      from inbound). trace-flags rules:
        - Preserve the inbound trace-flags byte when a valid inbound
          `traceparent` was accepted (a `sampled=0` upstream is not
          silently flipped to `sampled=1`).
        - When the trace was derived from `X-Cycles-Trace-Id` (no
          inbound W3C `traceparent`) or generated fresh by the server,
          default trace-flags = `01` (sampled).

- Standard event payload schema in the webhook prose: `request_id`
  contract strengthened to cover queued/deferred/async work, `trace_id`
  documented as an optional field that MUST be populated by conformant
  servers.

- Backward compatibility: purely additive. No field removals, no type
  changes, no new required fields on existing schemas. Old clients
  ignore the new response header; old subscribers ignore the new
  webhook headers; servers that don't yet implement the contract are
  already wire-compatible (OPTIONAL properties on ErrorResponse;
  additive response headers).

---

## v0.1.25 — 2026-04-16

_(revision 2026-04-16 — server-side sort on listReservations)_

- Companion change to the governance-admin v0.1.25.20
  revision. Closes the silent-wrong-answer hazard where a
  client-side sort applied over a cursor-paginated response
  only orders the loaded slice; under cursor pagination, the
  server's cursor order determines what appears on page N+1.
  A dashboard advertising "sort by expires_at_ms asc" while
  the server paginated by created_at_ms could hide the
  soonest-expiring reservations on a later page and never
  surface them.
- Adds two optional query parameters to listReservations
  (GET /v1/reservations):
    * sort_by: string enum [reservation_id, tenant,
      scope_path, status, reserved, created_at_ms,
      expires_at_ms]. Default when sort_by is provided but
      unset on the wire: created_at_ms.
      The `reserved` key sorts by the integer `amount` within
      each row; because the v0 single-unit-per-reservation
      invariant holds, this comparison is well-defined (no
      cross-unit conversion).
      The `scope_path` key sorts lexicographically over the
      server-derived canonical scope path string that
      ReservationSummary.scope_path already carries (e.g.
      "tenant:acme/workspace:prod/agent:x"). The `tenant`
      key sorts over Subject.tenant only (equivalent to
      the flat `tenant` filter already on this endpoint).
    * sort_dir: string enum [asc, desc]. Default "desc".
  When sort_by is provided, servers MUST return results in the
  requested order and MUST encode the sort key into the opaque
  cursor so subsequent pages continue in sort order. When
  omitted, servers use their previous default ordering (wire
  behavior unchanged for clients that never send these params).
- Servers MUST reject sort_by values outside the allowed enum
  with HTTP 400 INVALID_REQUEST. Servers MUST reject sort_dir
  values outside {asc, desc} with HTTP 400. Older servers that
  don't recognize the params MUST ignore them without error
  (additive-parameter guarantee).
- Cursor interaction: cursors returned under a given (sort_by,
  sort_dir, filters) tuple are only valid for continued
  pagination under that same tuple. Clients MUST reset the
  cursor when changing sort key or direction.
- Both ApiKeyAuth and AdminKeyAuth callers see the same
  parameter surface; admin callers paginating cross-tenant
  under their required `tenant` filter get the same
  server-ordered guarantee.
- Backward compatible: purely additive. No request or response
  schema changes. New shared `SortDirection` schema added
  under components/schemas (named "SortDirection"; inlining
  matches the governance-admin spec's v0.1.25.20 addition of
  the same name — each spec in the family carries its own
  definition since cross-spec $ref is not used in this
  companion-specs publication model).

---

## v0.1.25

_(revision 2026-04-13b — clarify admin-release audit discoverability)_

- Adds a NORMATIVE clause to releaseReservation's AUDIT block
  requiring that the audit-log entry be discoverable via the
  governance plane's GET /v1/admin/audit/logs endpoint. The
  earlier wording only required the entry to exist with the
  right actor_type tag — a conformant server could have
  written it to an isolated store that the admin dashboard
  can't read from, satisfying the letter of the spec while
  breaking the operational intent.
- Implementation detail (e.g. whether both planes share a
  store or whether cross-plane forwarding is used) is
  deliberately not specified — only the read-surface
  invariant is NORMATIVE.
- No schema or endpoint changes.

---

## v0.1.25 — 2026-04-13

_(revision 2026-04-13 — admin-on-behalf-of dual-auth on reservations)_

- Admin operators can now read and force-release reservations
  via the existing tenant-scoped endpoints, mirroring the
  dual-auth pattern established for createBudget / createPolicy /
  updatePolicy in the governance-admin spec v0.1.25.13.
- Three reservation operations gain AdminKeyAuth as an
  alternative security scheme:
    GET   /v1/reservations            (listReservations)
    GET   /v1/reservations/{id}       (getReservation)
    POST  /v1/reservations/{id}/release (releaseReservation)
- createReservation / commitReservation / extendReservation
  remain ApiKeyAuth-only by design — admin acting on those is
  a footgun (committing on behalf of a tenant takes from the
  tenant's budget but the tenant's audit trail wouldn't show
  their key as the actor). Force-release is the only legitimate
  admin lifecycle action.
- Semantic delta on the existing `tenant` query param of
  listReservations: REQUIRED (filter, not validation) when
  called with AdminKeyAuth; unchanged optional/validation
  behavior under ApiKeyAuth. Same single-param dual-semantic
  shape as the governance-admin admin reads. Omitting `tenant`
  under AdminKeyAuth MUST return 400 INVALID_REQUEST.
- Audit-log requirement (NORMATIVE) on admin-driven release:
  actor_type=admin_on_behalf_of, matching the existing tag
  server emits for createBudget / createPolicy. Callers SHOULD
  populate the optional `reason` body field with a structured
  tag for grep-ability.
- New security scheme declaration: AdminKeyAuth (apiKey,
  X-Admin-API-Key header) — same header the governance-admin
  spec already uses, so admin operators authenticate with one
  key against both planes.
- Backward compatible: ApiKey-only callers see no behavior
  change. Existing schemas (ReleaseRequest already has the
  optional `reason` field) need no modification.

---

## v0.1.25 — 2026-04-12

_(revision 2026-04-12 — document 400 on two remaining operations)_

- Completeness fix flagged by strict contract validation in
  runcycles/cycles-server. The runtime server correctly emits 400
  Bad Request on malformed JSON / missing required fields / invalid
  enum values — Spring's default behavior on @Valid violation and
  HttpMessageNotReadableException. Two operations were silent about
  400 in their response lists:
    - GET /v1/reservations/{reservation_id}
    - POST /v1/reservations/{reservation_id}/release
  Both now reference ErrorResponse on "400". All 9 runtime operations
  now document 400.
- Unblocks strict response-status validation in downstream contract
  tests: cycles-server's ContractValidationConfig can now remove its
  "validation.response.status.unknown" LevelResolver IGNORE — a
  separate follow-up in that repo.
- No existing response entries changed. Purely additive.

---

## v0.1.25 — 2026-04-01

_(initial 2026-04-01, revisions 2026-04-10 / 2026-04-11)_


Initial (2026-04-01):
- Added WEBHOOK EVENT GUIDANCE section documenting 40 event types across 6 categories,
  standard event payload schema, webhook delivery protocol, X-Cycles-Signature HMAC
  verification, retry/failure handling, retention policy, and extensibility contract.
- No new API endpoints — webhook guidance is informational, not normative.
- Runtime server implementations now emit events for reservation.denied,
  reservation.commit_overage, and budget state changes to a shared dispatch queue.

Error semantics refinements (2026-04-10, PR #25 — surfaced by
runcycles/cycles-client-rust#8 / runcycles/cycles-server#79):
- Broadened the normative UNIT_MISMATCH error-semantics block (section "ERROR
  SEMANTICS (NORMATIVE)") to enumerate all four runtime entry points that MAY
  return 400 UNIT_MISMATCH: (a) reserve, (b) commit, (c) event, (d) decide.
  Previously documented only commit and event; reserve and decide emissions were
  implemented by the reference server but undocumented.
- Recommended populated `details` object on 400 UNIT_MISMATCH responses from
  reserve / event / decide paths: `scope` (canonical scope where the mismatch
  was detected), `requested_unit` (the unit supplied by the client), and
  `expected_units` (array of units for which a budget does exist at that scope),
  so clients can self-correct without a separate lookup.
- Documented HTTP 404 response on POST /v1/reservations and POST /v1/events
  endpoints. The reference server has always emitted 404 with error=NOT_FOUND
  on these endpoints when no budget exists at the target scope in any unit, but
  the response was not previously declared in the endpoints' response list — a
  strict spec-conformance gap for client code generators building typed error
  unions from the spec. /v1/decide continues to return 200 DENY (with
  reason_code=BUDGET_NOT_FOUND) for the no-budget case; its response list is
  unchanged.

Wire-code naming + reason_code enumeration (2026-04-11, PR #26 — follow-up
cleanup to PR #25):
- Clarified that on the runtime plane, HTTP 404 uses the single `NOT_FOUND`
  error code for all resource-not-found conditions, with the `message` field
  carrying the specific reason (e.g. "Budget not found for provided scope: ...").
  `BUDGET_NOT_FOUND` is NOT a valid `error` wire value on the runtime plane —
  three passages added in PR #25 that had named it as such were rewritten.
  (The admin plane, `cycles-governance-admin-v0.1.25.yaml`, has its own
  `ErrorCode` enum which does include `BUDGET_NOT_FOUND` as a first-class
  wire code; that plane is unaffected.)
- Added new `DecisionReasonCode` schema under `components/schemas` — an
  OPEN string (not a closed enum) with documented known values and
  explicit extensibility language. Initial known values:
    BUDGET_EXCEEDED, BUDGET_FROZEN, BUDGET_CLOSED, BUDGET_NOT_FOUND,
    OVERDRAFT_LIMIT_EXCEEDED, DEBT_OUTSTANDING
  The schema includes per-value descriptions of the underlying condition
  each represents, and an explicit note that `reason_code` labels may
  overlap conceptually with `ErrorCode` entries (e.g. `BUDGET_EXCEEDED`
  appears in both sets) because they surface the same underlying budget
  state on different response types — `reason_code` on 200 DENY,
  `ErrorCode` on 4xx/5xx error bodies.
- Changed `DecisionResponse.reason_code` and
  `ReservationCreateResponse.reason_code` from inline free-form `type:
  string, maxLength: 128` to `$ref: '#/components/schemas/DecisionReasonCode'`.
  The referenced schema is an open string with documented known values,
  preserving the extensibility needed for companion extension specs
  (e.g., v0.1.26 adds ACTION_QUOTA_EXCEEDED, ACTION_KIND_DENIED,
  ACTION_KIND_NOT_ALLOWED).
- Why OPEN, not a closed enum: the v0 protocol is designed for additive
  companion extensions. A closed enum at the base would force extensions
  to either (a) invent a new reason_code field and live with a dual-
  population pattern, or (b) require base spec version bumps for every
  new extension reason code. Neither is sustainable. The open string with
  documented known values preserves type-safety via codegen conventions
  (SDK codegen SHOULD produce a string-subtype with constants for known
  values) while keeping extensibility intact.
- Clients MUST gracefully handle unknown `reason_code` values — log them
  and map to generic DENY handling. Strict validators MUST NOT reject
  unknown values.
- **No wire-format change.** All refinements document or narrow existing
  behavior — the reference server was already conformant with the updated
  spec. No protocol version bump required.
- SERVER IMPLEMENTATION NOTE (non-normative): server implementations MAY
  represent `reason_code` internally as a closed typed structure (e.g., a
  language-native enum) covering exactly the values the server actually
  emits, without violating the spec's openness. The "Clients MUST gracefully
  handle unknown values" and "SDK code MUST NOT reject unknown values"
  clauses target CLIENT consumers (language SDKs, downstream services,
  dashboards) of server responses, not reference server internals. A server
  is the EMITTER of `reason_code`, not a consumer, and its idempotency
  replay cache — the only place it ever deserializes a `reason_code` value —
  contains only values the server itself previously wrote. A typed
  closed enum on the server side therefore gives compile-time safety for
  the emitter's own emission set while the wire format remains spec-open
  for extension-plane flexibility. This is the standard "tighter subset
  is still compliant" pattern.

---

## v0.1.24 — 2026-03-24

- BREAKING: Changed default CommitOveragePolicy from REJECT to ALLOW_IF_AVAILABLE.
  Clients relying on implicit REJECT must now set overage_policy explicitly.
- Changed ALLOW_IF_AVAILABLE commit behavior: when remaining budget cannot cover
  the full overage delta, the commit now succeeds with a capped charge
  (estimate + available remaining) instead of returning 409 BUDGET_EXCEEDED.
  Scopes where the full delta could not be covered are marked is_over_limit=true,
  blocking future reservations until reconciled.
- Extended is_over_limit semantics: now also set by ALLOW_IF_AVAILABLE when
  overage delta is capped, in addition to ALLOW_WITH_OVERDRAFT debt scenarios.
- Updated CommitResponse.charged description: charged may be less than actual
  when ALLOW_IF_AVAILABLE caps the overage delta.
- Added charged field to EventCreateResponse: optional Amount present when
  ALLOW_IF_AVAILABLE caps the event charge to remaining budget.
- Added ErrorCode values: BUDGET_FROZEN, BUDGET_CLOSED, MAX_EXTENSIONS_EXCEEDED.
  These were already used by the reference server but missing from the spec enum.

---

## v0.1.23 — 2026-02-21

- Renamed Subject.toolGroup → Subject.toolset across all endpoints, schemas,
  and normative text for consistency with scope hierarchy naming conventions.
- Added ALLOW_WITH_OVERDRAFT semantics to EventCreateRequest.overage_policy
  (finding: behavior was previously unspecified for events).
- Clarified DecisionResponse.decision description: DENY is a valid live-path
  outcome on /decide; removed erroneous dry_run framing copied from
  ReservationCreateResponse.
- Added ERROR SEMANTICS precedence rule: when is_over_limit=true, server MUST
  return 409 OVERDRAFT_LIMIT_EXCEEDED for new reservations, taking precedence
  over DEBT_OUTSTANDING even when debt > 0.
- Added DEBT/OVERDRAFT STATE normative block to /decide: server SHOULD return
  decision=DENY under debt or over-limit conditions; MUST NOT return 409.

---

## v0.1.22 — 2026-02-18

- Added overdraft/debt model: ALLOW_WITH_OVERDRAFT overage policy, debt and
  overdraft_limit fields on Balance, is_over_limit flag, OVERDRAFT_LIMIT_EXCEEDED
  and DEBT_OUTSTANDING error codes.
- Added SignedAmount schema to support negative remaining in overdraft state.
- Added OVERDRAFT RECONCILIATION normative section and OVERDRAFT MONITORING
  guidance section including recommended alerting thresholds and operator runbook.
- Added OVER-LIMIT BLOCKING normative block to createReservation.

---

## v0.1.0 → v0.1.21

- Initial protocol definition: reserve/commit/release lifecycle, idempotency,
  scope derivation, /decide, /balances, /events, dry_run shadow mode,
  reservation extend/list/get endpoints, soft enforcement via Caps.
