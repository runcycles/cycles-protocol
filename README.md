[![Validate OpenAPI Spec Suite](https://github.com/runcycles/cycles-protocol/actions/workflows/validate.yml/badge.svg)](https://github.com/runcycles/cycles-protocol/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

# Cycles Protocol — Runtime budget and action authority for AI agents

**Open protocol for AI agent governance: enforce cost limits, action permissions, and multi-tenant policies before LLM tools execute.** Concurrency-safe budget reservations, risk-classified action kinds, and webhook-based event delivery for autonomous agent runtimes.

Cycles is the protocol layer that ensures agents cannot authorize more spend or take riskier actions than policy allows — even when dozens of them run concurrently across providers (OpenAI, Anthropic, MCP servers, OpenAI Agents SDK, custom tools).

## Start here

- **Implementing a compatible server?** Read [`CONFORMANCE.md`](CONFORMANCE.md) — it's the authoritative MUST/SHOULD/MAY statement.
- **Want the runtime API?** Start with [`cycles-protocol-v0.yaml`](cycles-protocol-v0.yaml) (4 core ops: reserve, commit, release, extend).
- **Want governance/admin operations?** See [`cycles-governance-admin-v0.1.25.yaml`](cycles-governance-admin-v0.1.25.yaml).
- **Want upcoming action-level governance?** See the v0.1.26 extension specs ([protocol extensions](cycles-protocol-extensions-v0.1.26.yaml), [action kinds](cycles-action-kinds-v0.1.26.yaml), [governance extensions](cycles-governance-extensions-v0.1.26.yaml)).

---

**Spec suite:** v0.1.26 &middot; **Current conformance target:** v0.1.25 &middot; **Runtime base:** v0.1.25 &middot; **Governance base:** v0.1.25.29 (semantic_base 0.1.25.9) &middot; **API path:** `/v1` &middot; **License:** Apache 2.0

The Cycles spec suite is organized by conformance status. The **current conformance target is v0.1.25** — the version runcycles' own reference servers implement today. v0.1.26 specs are published in this repo but not yet required; they are the **upcoming** target and will be promoted to normative once the reference stack implements them.

| Tier | Files | Status |
|---|---|---|
| **Normative (v0.1.25)** | [`cycles-protocol-v0.yaml`](cycles-protocol-v0.yaml) | A conformant server MUST implement the 4 core runtime ops (`createReservation`, `commitReservation`, `releaseReservation`, `extendReservation`). Of the 5 endpoints this spec marks OPTIONAL / nice-to-have, `getBalances` is a cross-plane MUST because `cycles-governance-admin-v0.1.25.yaml` re-declares it as normative; the remaining 4 (`decide`, `listReservations`, `getReservation`, `createEvent`) are SHOULD. See [`CONFORMANCE.md`](CONFORMANCE.md). |
| **Mixed (v0.1.25)** | [`cycles-governance-admin-v0.1.25.yaml`](cycles-governance-admin-v0.1.25.yaml) | Mostly runcycles' reference admin API (implementers MAY diverge), but eight cross-plane operations and selected schemas (`Event`, `EventType`, `EventData*`, `WebhookDelivery`, `WebhookRetryPolicy`, `Permission`) are normative via `x-conformance` labels. See [`CONFORMANCE.md`](CONFORMANCE.md). |
| **Upcoming (v0.1.26)** | [`cycles-protocol-extensions-v0.1.26.yaml`](cycles-protocol-extensions-v0.1.26.yaml), [`cycles-action-kinds-v0.1.26.yaml`](cycles-action-kinds-v0.1.26.yaml), [`cycles-governance-extensions-v0.1.26.yaml`](cycles-governance-extensions-v0.1.26.yaml) | Published but not yet required for conformance. SHOULD today; will become MUST once the reference stack ships v0.1.26 support. |

See [`CONFORMANCE.md`](CONFORMANCE.md) for the authoritative MUST / SHOULD / MAY statement, and [`cycles-spec-index.yaml`](cycles-spec-index.yaml) for the composition manifest and merge recipes.

> **v0.1.26 (upcoming)** adds action-level governance on top of the stable v0.1.25 runtime base:
> - **Action kind registry** — 62 built-in kinds with risk classification and governance policy
> - **Per-kind and risk-class quotas** — with burst protection (`per_minute_tumbling`) and threshold warnings
> - **Access control lists** — `allowed_action_kinds` / `denied_action_kinds` on policies
> - **Observe mode** — shadow rollout with `observed_denied` / `observed_allowed` events
> - **Enriched deny context** — `DenyDetail` with quota violation info, blocked scope/policy, suggested fixes
> - **Counter reset** — incident response endpoint for stuck per_run counters
>
> The suite ships as companion specs: [`cycles-protocol-v0.yaml`](cycles-protocol-v0.yaml) (runtime base), [`cycles-protocol-extensions-v0.1.26.yaml`](cycles-protocol-extensions-v0.1.26.yaml) (runtime extension), [`cycles-action-kinds-v0.1.26.yaml`](cycles-action-kinds-v0.1.26.yaml) (registry), [`cycles-governance-admin-v0.1.25.yaml`](cycles-governance-admin-v0.1.25.yaml) (admin base), and [`cycles-governance-extensions-v0.1.26.yaml`](cycles-governance-extensions-v0.1.26.yaml) (admin extension). See [`cycles-spec-index.yaml`](cycles-spec-index.yaml) for the composition manifest and merge recipes.

---

## Why Cycles

AI agents do not just spend money autonomously. They call LLMs, execute tools, retry on failure, fan out in parallel, and spawn sub-agents — creating not only cost, but **risk and operational exposure**.

That exposure can be financial, but it can also be consequential: records changed, emails sent, jobs triggered, APIs called, files overwritten, or external systems affected. Traditional cost controls assume predictable, human-initiated requests. Agent runtimes break those assumptions.

Cycles exists because **budget and exposure are safety properties in agentic systems, not billing afterthoughts.** It provides a protocol-level enforcement point for governing spend and actions before execution, with correctness under concurrency, retries, and partial failures.

## Conformance

Cycles is a minimum protocol. A conformant **v0.1.25** server MUST implement 12 operations (4 core runtime reserve/commit/release/extend, plus 8 cross-plane event / webhook / auth-introspection — including `getBalances`, which the admin spec re-declares as normative) and SHOULD implement an additional 4 runtime operations (decide, listReservations, getReservation, createEvent) that the spec marks OPTIONAL — together making up the 16-operation v0.1.25 protocol surface. Otherwise the server is free to implement tenant management, budget provisioning, key rotation, and audit UX however it likes. The additional v0.1.26 surface (action-kind registry + governance extensions, ~6 more ops) is upcoming and SHOULD-level today.

[`CONFORMANCE.md`](CONFORMANCE.md) is the authoritative statement of what a Cycles implementation MUST, SHOULD, and MAY do — scoped to the current v0.1.25 conformance target, with v0.1.26 listed under SHOULD / upcoming. Operations across the spec suite carry an `x-conformance` OpenAPI extension (`normative` or `reference`) so tooling can filter by conformance status within each spec.

## When to use Cycles

- You run **agents that call paid APIs or perform consequential actions** and need hard limits on spend, permissions, or total exposure per tenant, workspace, or agent.
- You need **concurrency-safe enforcement** — multiple agents or threads acting against the same budget or risk boundary at the same time.
- You want a **single control layer across providers and tools** instead of relying on fragmented limits in OpenAI, Anthropic, Google, SaaS APIs, and internal systems.
- You're building **multi-tenant platforms** where tenants define budgets or policies and you must guarantee isolation and bounded execution.
- You need to stop **runaway loops, retries, or fan-out behavior** before they create unacceptable cost or side effects.

Cycles is *not* needed for single-user scripts, free-tier-only workloads, or environments where overruns and unintended actions carry no meaningful consequence.

## What Cycles prevents

- **Runaway exposure** — agents loop, retry, or fan out past safe limits.
- **Double settlement** — the same economic action is committed more than once.
- **Concurrency overruns** — parallel agents collectively exceed a shared budget or boundary.
- **Too-late control** — alerts arrive only after spend or side effects already happened.

## Who it's for

- **Platform teams** building multi-tenant agent runtimes
- **Framework authors** integrating budget enforcement into agent SDKs and orchestration layers
- **Enterprise operators** who need audit-grade accountability per tenant, workspace, workflow, or agent
- **Gateway builders** enforcing shared spend policy across multiple LLM and tool providers
  
## Execution model

Cycles sits **between** the agent and the downstream system. Before calling a model, tool, API, or other consequential service, the agent asks Cycles for permission first, then reports back what it actually consumed or did.

```
Agent ──► Cycles (reserve) ──► Agent ──► Downstream API ──► Agent ──► Cycles (commit)
```

Cycles is **synchronous and blocking by design**: the reserve call returns `ALLOW` or `ALLOW_WITH_CAPS` before the agent acts, or rejects with a `409 BUDGET_EXCEEDED` error. This is what makes budget enforcement deterministic. There is no post-facto reconciliation window where spend can leak through.

Cycles is **not a proxy**. It does not sit in the data path or see request/response payloads. It only tracks cost metadata (who, what, how much). The agent is responsible for calling the downstream API and reporting actual cost on commit.

## How it works

```
1. Reserve     Lock estimated cost before the action runs.
2. Execute     Call the LLM / tool / API.
3. Commit      Record actual cost; unused budget is released automatically.
4. Release     Or cancel — full budget is returned, no charge.
```

**Tiny example:**
Examples use integer-denominated units to keep accounting exact and portable across implementations.
```jsonc
// Reserve $0.005 for an LLM call
POST /v1/reservations
{
  "idempotency_key": "req-abc-123",
  "subject": { "tenant": "acme", "agent": "support-bot" },
  "action":  { "kind": "llm.completion", "name": "openai:gpt-4o" },
  "estimate": { "unit": "USD_MICROCENTS", "amount": 500000 },
  "ttl_ms": 30000
}
// → { "decision": "ALLOW", "reservation_id": "rsv_1a2b3c" }

// After the call, commit actual spend ($0.0042)
POST /v1/reservations/rsv_1a2b3c/commit
{ "idempotency_key": "commit-abc-123", "actual": { "unit": "USD_MICROCENTS", "amount": 420000 } }
// → delta automatically released back to budget
```

## Intended use

**Cycles is a protocol specification, not a product**. 
It defines the API contract — request/response schemas, lifecycle rules, and invariants — so that:

- **Platform teams** implement a Cycles-compliant server inside their infrastructure (or adopt an open-source implementation).
- **SDK authors** build thin client libraries that wrap reserve/commit/release into idiomatic helpers for Python, TypeScript, Go, etc.
- **Agent frameworks** integrate Cycles as a middleware or plugin, making budget enforcement automatic for every tool call.

A typical deployment looks like: agent framework → Cycles SDK → Cycles server (your infra) → budget database. The protocol is intentionally minimal so it can be backed by Postgres, Redis, DynamoDB, or an in-memory store depending on your scale and durability needs.

### Python client

A production-ready Python client is available at [cycles-client-python](https://github.com/runcycles/cycles-client-python):

```bash
pip install runcycles
```

```python
from runcycles import CyclesClient, CyclesConfig, cycles, set_default_client

config = CyclesConfig(base_url="http://localhost:7878", api_key="cyc_live_...", tenant="acme")
client = CyclesClient(config)
set_default_client(client)

@cycles(estimate=1000, action_kind="llm.completion", action_name="gpt-4o")
def call_llm(prompt: str) -> str:
    return invoke_model(prompt)

result = call_llm("Hello")  # reserve → execute → commit
```

> **Need an API key?** API keys are created via the Cycles Admin Server. See the [deployment guide](https://runcycles.io/quickstart/deploying-the-full-cycles-stack#step-3-create-an-api-key) or [API Key Management](https://runcycles.io/how-to/api-key-management-in-cycles).

The `@cycles` decorator wraps any function in a reserve → execute → commit lifecycle with automatic heartbeat extensions and commit retry. Both sync and async clients are supported. See the [Python quickstart](https://runcycles.io/quickstart/getting-started-with-the-python-client) for full documentation.

### Reference server

A reference implementation is available at [cycles-server](https://github.com/runcycles/cycles-server). Run it with Docker — no Java or build tools required:

```bash
# Pull the pre-built image and start
docker compose -f docker-compose.prod.yml up
```

Or build from source:

```bash
git clone https://github.com/runcycles/cycles-server.git
cd cycles-server
docker compose up --build
```

The server starts on port 7878 with interactive API docs at http://localhost:7878/swagger-ui.html. Pre-built images are published to `ghcr.io/runcycles/cycles-server`.

> **Note:** The runtime server handles budget enforcement but cannot create tenants, API keys, or budgets on its own. For a complete setup, you also need runcycles' [reference admin server](https://github.com/runcycles/cycles-server-admin) (management plane) — which implements the mostly-reference [`cycles-governance-admin-v0.1.25.yaml`](cycles-governance-admin-v0.1.25.yaml) spec. That file is classified as Mixed: the tenant / budget / policy / API-key / audit CRUD surface is reference (implementers MAY adopt it, diverge from it, or replace it with their own provisioning mechanism), while a small set of cross-plane operations and schemas inside the same file are normative — see [`CONFORMANCE.md`](CONFORMANCE.md). The easiest path to try the reference stack is the one-command quickstart:
>
> ```bash
> git clone https://github.com/runcycles/cycles-server.git
> cd cycles-server
> ./quickstart.sh
> ```
>
> This starts the full stack (Redis + runtime server + admin server), creates a tenant, API key, and funded budget, and verifies the complete lifecycle. See the [full deployment guide](https://runcycles.io/quickstart/deploying-the-full-cycles-stack) for details.

## Why not just…
| Approach | Gap Cycles fills |
|----------|-----------------|
| **Rate limiting** | Caps request volume, not dollar cost. A single expensive call still blows the budget. |
| **Observability / alerts** | Tells you *after* the money is gone. Cycles blocks the spend *before* it happens. |
| **Provider-side budgets** | Per-provider, not cross-provider. Can't enforce org-wide policy across OpenAI + Anthropic + Google + tool calls in one place. |
| **LLM Proxies & Gateways** | Sit between you and the LLM provider — but agents do more than call LLMs. Tool calls, database writes, emails, deployments are all uninstrumented. Gateways also report after the call completes, not before it starts. |

## Core guarantees

1. **Atomic reservation** — budget is locked across all affected scopes in one step; no partial locks.
2. **Concurrency-safe enforcement** — shared budgets cannot be oversubscribed by simultaneous reserve operations.
3. **Idempotent commit and release** — retries are safe; the same action cannot settle twice.
4. **No unaccounted spend** — the ledger remains internally consistent: `remaining = allocated - spent - reserved - debt`.

## Design boundaries

Cycles does not proxy downstream requests, execute tools, price provider calls for you, or manage budget funding in v0. It governs reservation and settlement of economic exposure around those systems.

---

# Protocol specification

Everything below is the full protocol reference. For the OpenAPI 3.1.0 definition, see [`cycles-protocol-v0.yaml`](cycles-protocol-v0.yaml).

## Table of Contents

- [Reservation Lifecycle](#reservation-lifecycle)
- [API Reference](#api-reference)
- [Subject Hierarchy](#subject-hierarchy)
- [Units](#units)
- [Overage Policies](#overage-policies)
- [Debt and Overdraft](#debt-and-overdraft)
- [Idempotency](#idempotency)
- [Authentication and Tenancy](#authentication-and-tenancy)
- [Response Headers](#response-headers)
- [Correlation and Tracing](#correlation-and-tracing)
- [Key Schemas](#key-schemas)
- [Pagination](#pagination)
- [Error Codes](#error-codes)
- [SDK Guidance](#sdk-guidance)
- [Operator Guidance](#operator-guidance)
- [Non-Goals (v0)](#non-goals-v0)
- [Evolution Contract](#evolution-contract)

---

## Reservation Lifecycle

```
    ┌──────────┐
    │  Reserve │  Atomically lock estimated budget
    └────┬─────┘
         │
    ┌────▼─────┐
    │  ACTIVE  │  reservation_id returned, TTL starts
    └────┬─────┘
         │
    ┌────┴────────────┬─────────────┐
    │                 │             │
┌───▼────┐     ┌──────▼─────┐  ┌────▼─────┐
│ Commit │     │  Release   │  │  Expire  │
│ actual │     │  (cancel)  │  │ (timeout)│
└───┬────┘     └──────┬─────┘  └─────┬────┘
    │                 │              │
    │  auto-releases  │  returns     │  budget
    │  delta if       │  full        │  unlocked
    │  actual<reserved│  amount      │  by server
    ▼                 ▼              ▼
 COMMITTED         RELEASED       EXPIRED
```

### Quick Example

```bash
# 1. Reserve budget for an LLM call
curl -X POST https://api.cycles.local/v1/reservations \
  -H "X-Cycles-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "req-abc-001",
    "subject": { "tenant": "acme", "agent": "support-bot" },
    "action": { "kind": "llm.completion", "name": "openai:gpt-4o" },
    "estimate": { "unit": "USD_MICROCENTS", "amount": 500000 },
    "ttl_ms": 30000,
    "overage_policy": "REJECT"
  }'
# → { "decision": "ALLOW", "reservation_id": "rsv_1a2b3c", "expires_at_ms": 1709312345678, ... }

# 2. Execute the action, then commit actual spend
curl -X POST https://api.cycles.local/v1/reservations/rsv_1a2b3c/commit \
  -H "X-Cycles-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "commit-abc-001",
    "actual": { "unit": "USD_MICROCENTS", "amount": 420000 },
    "metrics": { "tokens_input": 1200, "tokens_output": 800, "model_version": "gpt-4o-2024-05" }
  }'
# → { "status": "COMMITTED", "charged": { ... }, "released": { ... }, ... }
# Note: "released" is only present when actual < reserved

# 3. Or release if the action was cancelled
curl -X POST https://api.cycles.local/v1/reservations/rsv_1a2b3c/release \
  -H "X-Cycles-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "idempotency_key": "release-abc-001", "reason": "user cancelled" }'
# → { "status": "RELEASED", "released": { ... } }
```

---

## API Reference

### Decisions (optional preflight)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/decide` | Check if an action fits within budget. Returns `ALLOW`, `ALLOW_WITH_CAPS`, or `DENY`. Does **not** create a reservation. Response may include `retry_after_ms`. |

Use `/decide` for soft-landing checks before reserving. A subsequent `/reservations` call can still fail if concurrent activity depletes budget between the two calls.

### Reservations (core)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/reservations` | Reserve budget atomically. Returns `reservation_id` with decision `ALLOW` or `ALLOW_WITH_CAPS`. |
| `GET` | `/v1/reservations` | List reservations (optional, for recovery/debug). |
| `GET` | `/v1/reservations/{id}` | Get reservation details (optional, for debug). |
| `POST` | `/v1/reservations/{id}/commit` | Commit actual spend. Auto-releases delta if actual < reserved. |
| `POST` | `/v1/reservations/{id}/release` | Release unused reservation back to budget. |
| `POST` | `/v1/reservations/{id}/extend` | Extend TTL as a heartbeat for long-running operations. |

### Balances (operator visibility)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/balances` | Query current budget balances across scopes. |

### Events (optional post-only accounting)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/events` | Record spend without a prior reservation (when pre-estimation is unavailable). Returns `201`. |

---

## Subject Hierarchy

Every request targets a **Subject** — a dimension bag describing where in the hierarchy the budget applies. At least one standard field (tenant, workspace, app, workflow, agent, or toolset) must be provided. A Subject containing only `dimensions` is invalid (`400 INVALID_REQUEST`).

```
tenant → workspace → app → workflow → agent → toolset
```

| Field | Description | Max Length |
|-------|-------------|-----------|
| `tenant` | Top-level organizational boundary | 128 |
| `workspace` | Workspace within a tenant | 128 |
| `app` | Application | 128 |
| `workflow` | Workflow or run | 128 |
| `agent` | Individual agent | 128 |
| `toolset` | Group of tools | 128 |
| `dimensions` | Optional custom key-value pairs for enterprise taxonomies. Keys should match `^[a-z0-9_.-]+$`. v0 servers may ignore for budgeting but must accept and round-trip. | 16 keys, 256 chars/value |

The server derives canonical scope identifiers from the Subject. Scope ordering in `affected_scopes` is always canonical: tenant, workspace, app, workflow, agent, toolset.

---

## Units

| Unit | Description | Precision |
|------|-------------|-----------|
| `USD_MICROCENTS` | 10⁻⁶ cents (10⁻⁸ dollars) | int64; max ~$92.2B |
| `TOKENS` | Integer token counts | int64 |
| `CREDITS` | Generic integer units | int64 |
| `RISK_POINTS` | Generic integer units (optional) | int64 |

A reservation lifecycle is denominated in exactly **one unit**. Reserving, committing, or recording a direct event with a unit that doesn't match the stored budget unit returns `400 UNIT_MISMATCH`. When the target scope has a budget in a different unit, the error response's `details` object includes `scope`, `requested_unit`, and `expected_units` so clients can self-correct.

---

## Overage Policies

Controls what happens when actual spend exceeds the reserved estimate at commit time.

| Policy | Behavior |
|--------|----------|
| `REJECT` (default) | Reject the commit. SDK should add 10-20% estimation buffer. |
| `ALLOW_IF_AVAILABLE` | Commit succeeds only if the delta fits in remaining budget. Atomic check-and-charge. |
| `ALLOW_WITH_OVERDRAFT` | If remaining budget covers the delta, commit normally. Otherwise, commit succeeds if `(current_debt + delta) <= overdraft_limit`, creating debt; remaining can go negative. |

The same policies apply to `/events`.

---

## Debt and Overdraft

When `overage_policy=ALLOW_WITH_OVERDRAFT` is used, the protocol supports controlled deficit spending:

- **`debt`** — actual consumption that occurred when insufficient budget existed. Must be repaid via out-of-band funding operations before new reservations are allowed.
- **`overdraft_limit`** — maximum debt permitted per scope. If absent or 0, no overdraft is allowed.
- **`is_over_limit`** — set to `true` when `debt > overdraft_limit` (can happen due to concurrent commits). Blocks **all** new reservations on that scope until reconciled.

### Concurrency semantics

The overdraft limit check is per-commit and is **not** atomic across concurrent commits. Multiple commits may each individually pass but collectively push debt past the limit. This is by design — the actions already happened — and the scope enters over-limit state until an operator reconciles.

### Over-limit blocking

When any affected scope has `is_over_limit=true`:
- New reservations return `409 OVERDRAFT_LIMIT_EXCEEDED`
- Existing active reservations can still be committed or released
- `/decide` SHOULD return `decision=DENY` with `reason_code` (`DEBT_OUTSTANDING` or `OVERDRAFT_LIMIT_EXCEEDED`) — must never return 409 for these conditions

---

## Idempotency

All mutating endpoints support idempotency via `idempotency_key` (body field) and/or `X-Idempotency-Key` (header). If both are provided, they must match.

- Scoped per `(effective_tenant, endpoint, idempotency_key)`.
- Replay of a previously successful request returns the **original response** (including server-generated IDs).
- Same key with a different payload returns `409 IDEMPOTENCY_MISMATCH`.
- Servers should use canonical JSON (RFC 8785) for payload comparison.

---

## Authentication and Tenancy

- **Auth:** `X-Cycles-API-Key` header on every request.
- **Effective tenant:** Derived by the server from the API key or auth context.
- **Validation:** If `subject.tenant` is provided, it must match the effective tenant — otherwise `403 FORBIDDEN`.
- **Reservation ownership:** Every reservation is bound to its creating tenant. GET, commit, release, or extend on a reservation owned by a different tenant must return `403 FORBIDDEN`.
- **Scoping:** All queries (reservations, balances, events) are automatically tenant-scoped. Cross-tenant balance queries must return `403 FORBIDDEN`.

---

## Response Headers

All responses may include these headers:

| Header | Description |
|--------|-------------|
| `X-Request-Id` | Unique request identifier for debugging (one HTTP request) |
| `X-Cycles-Trace-Id` | W3C Trace Context-compatible trace identifier (32 lowercase hex chars). Emitted on every response. Links the request, its audit entry, emitted events, and outbound webhook deliveries under one logical operation. See [Correlation and Tracing](#correlation-and-tracing). |
| `X-Cycles-Tenant` | Effective tenant identifier derived from auth context (optional in v0) |
| `X-RateLimit-Remaining` | Requests remaining in current rate-limit window (optional in v0) |
| `X-RateLimit-Reset` | Unix timestamp (seconds) when the rate limit resets (optional in v0) |

### Correlation and Tracing

Three correlation identifiers travel together:

| Field | Grain | Source | Purpose |
|---|---|---|---|
| `request_id` | One HTTP request | Server | "What single API call caused this side effect?" |
| `trace_id` | Logical operation across N requests | Client (`traceparent` or `X-Cycles-Trace-Id` header) or server-generated | "What user-intent / distributed trace am I inside?" |
| `correlation_id` | Event-stream cluster (window / run / denial) | Server (deterministic hash) | "Which other events share my window or run?" |

**Inbound header precedence** (server extracts `trace_id` from the first rule that matches):

1. `traceparent` header, if present and valid per W3C Trace Context §3.2 (version `00`, non-all-zero trace-id and span-id).
2. Else `X-Cycles-Trace-Id` header, if present and matches `^[0-9a-f]{32}$` and is not all-zero.
3. Else the server generates a fresh 128-bit trace-id (32 lowercase hex chars; all-zero is re-rolled).

Malformed correlation headers are treated as absent — the server MUST NOT reject a request on a malformed `traceparent` or `X-Cycles-Trace-Id`. If both are present and disagree, `traceparent` wins.

**Outbound propagation:** every response carries `X-Cycles-Trace-Id`. Outbound webhook deliveries carry `X-Cycles-Trace-Id`, a freshly constructed `traceparent` (with a new outbound span-id; inbound trace-flags preserved when the inbound `traceparent` was valid, default `01` otherwise), and `trace_id` in the event envelope body. Admin-plane `Event` and `AuditLogEntry` schemas carry `trace_id`, and `listEvents` / `listAuditLogs` accept `trace_id` and `request_id` as filter parameters.

The authoritative contract lives in `cycles-protocol-v0.yaml`'s `CORRELATION AND TRACING` preamble section and binds every plane.

---

## Key Schemas

### Action

Describes the operation being budgeted. Required on `/decide`, `/reservations`, and `/events`.

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `kind` | string | yes | maxLength 64 | Action type. Format: `<category>.<operation>` (e.g., `llm.completion`, `tool.search`, `db.query`) |
| `name` | string | yes | maxLength 256 | Provider/model/tool identifier (e.g., `openai:gpt-4o`, `web.search`) |
| `tags` | string[] | no | maxItems 10, 64 chars each | Optional policy tags (e.g., `["prod", "customer-facing"]`) |

### Caps

Soft-landing constraints returned when `decision=ALLOW_WITH_CAPS` on `/decide` or `/reservations`. Must be absent when decision is `ALLOW` or `DENY`.

| Field | Type | Description |
|-------|------|-------------|
| `max_tokens` | integer | Token limit |
| `max_steps_remaining` | integer | Step budget |
| `tool_allowlist` | string[] | Allowed tools (allowlist takes precedence over denylist) |
| `tool_denylist` | string[] | Denied tools (ignored if allowlist is non-empty) |
| `cooldown_ms` | integer | Rate-limiting cooldown in milliseconds |

**Precedence:** If `tool_allowlist` is non-empty, only those tools are allowed and `tool_denylist` is ignored. Tool names are case-sensitive and match `Action.name` exactly.

### StandardMetrics

Optional metrics included in commit and event requests for observability.

| Field | Type | Description |
|-------|------|-------------|
| `tokens_input` | integer | Input tokens consumed |
| `tokens_output` | integer | Output tokens generated |
| `latency_ms` | integer | Total operation latency in milliseconds |
| `model_version` | string | Actual model/tool version used (maxLength 128) |
| `custom` | object | Arbitrary additional metrics (free-form key-value) |

### ErrorResponse

All error responses share this structure:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error` | ErrorCode | yes | Machine-readable error code (see [Error Codes](#error-codes)) |
| `message` | string | yes | Human-readable error description |
| `request_id` | string | yes | Request identifier for debugging (one HTTP request) |
| `trace_id` | string | no | W3C Trace Context-compatible trace identifier (`^[0-9a-f]{32}$`). Links this error to the logical operation it belongs to. See [Correlation and Tracing](#correlation-and-tracing). |
| `details` | object | no | Additional context (free-form) |

### Amount

Non-negative quantity with a unit. Used for `estimate`, `actual`, `reserved`, `charged`, etc.

| Field | Type | Description |
|-------|------|-------------|
| `unit` | UnitEnum | One of `USD_MICROCENTS`, `TOKENS`, `CREDITS`, `RISK_POINTS` |
| `amount` | int64 | Non-negative integer (`minimum: 0`) |

`SignedAmount` is identical but allows negative values — used only for `Balance.remaining` which can go negative in overdraft state.

---

## Pagination

List endpoints (`GET /v1/reservations`, `GET /v1/balances`) support cursor-based pagination:

| Parameter/Field | Location | Description |
|-----------------|----------|-------------|
| `limit` | query param | Max results per page (1-200, default 50) |
| `cursor` | query param | Opaque cursor from a previous response |
| `next_cursor` | response body | Cursor for the next page (if any) |
| `has_more` | response body | `true` if more results are available |

### Balance query requirements

`GET /v1/balances` requires at least one subject filter (`tenant`, `workspace`, `app`, `workflow`, `agent`, or `toolset`). Omitting all filters returns `400 INVALID_REQUEST`. The `include_children` query parameter (boolean, default `false`) may be ignored by v0 implementations.

---

## Error Codes

| HTTP | Error Code | When |
|------|-----------|------|
| 400 | `INVALID_REQUEST` | Malformed request, missing required fields |
| 400 | `UNIT_MISMATCH` | Reserve/commit/event unit doesn't match the reservation's unit or the stored budget unit for the target scope. When a budget exists at the scope in a different unit, reserve and event responses populate `details.scope`, `details.requested_unit`, and `details.expected_units`. |
| 401 | `UNAUTHORIZED` | Missing or invalid API key |
| 403 | `FORBIDDEN` | Tenant mismatch or ownership violation |
| 404 | `NOT_FOUND` | Reservation never existed |
| 409 | `BUDGET_EXCEEDED` | Insufficient budget with `REJECT` or `ALLOW_IF_AVAILABLE` |
| 409 | `BUDGET_FROZEN` | Budget scope is frozen; operations blocked until unfrozen |
| 409 | `BUDGET_CLOSED` | Budget scope is permanently closed |
| 409 | `RESERVATION_FINALIZED` | Reservation already committed or released |
| 409 | `IDEMPOTENCY_MISMATCH` | Same key, different payload |
| 409 | `OVERDRAFT_LIMIT_EXCEEDED` | Debt would exceed limit, or scope is over-limit |
| 409 | `DEBT_OUTSTANDING` | Debt > 0 blocks new reservations |
| 409 | `MAX_EXTENSIONS_EXCEEDED` | Tenant `max_reservation_extensions` limit reached |
| 410 | `RESERVATION_EXPIRED` | Commit/release: beyond `expires_at_ms + grace_period_ms`. Extend: beyond `expires_at_ms` (no grace period). |
| 429 | *(rate limiting)* | Server-side throttling (optional in v0). Not used for budget exhaustion. |
| 500 | `INTERNAL_ERROR` | Server error |

Error precedence for reservations: `OVERDRAFT_LIMIT_EXCEEDED` takes priority over `DEBT_OUTSTANDING` when `is_over_limit=true`.

---

## SDK Guidance

When building an SDK or client integration:

- **Keep TTL short** (10-30s) to limit zombie reservations from client crashes.
- **Buffer estimates** by 10-20% when using `overage_policy=REJECT`.
- **Chunk long operations** — prefer multiple small reserve/commit cycles over one large reservation.
- **Use `/extend` as a heartbeat** for long-running agent workflows instead of setting large TTLs. Extension is relative to the current `expires_at_ms`, not request time.
- **Slow-start pattern** — begin with small reserves and increase gradually for bursty workloads.
- **Dry-run mode** (`dry_run: true`) — use for safe rollout and testing. No balances are modified, no persistence, no commit/release needed. In dry-run responses: `reservation_id` and `expires_at_ms` are absent; `affected_scopes` is always populated; if `decision=ALLOW_WITH_CAPS`, `caps` must be present; if `decision=DENY`, `reason_code` should be populated as the primary diagnostic signal.

### Reservation parameters

| Parameter | Range | Default | Notes |
|-----------|-------|---------|-------|
| `ttl_ms` | 1s – 24h | 60s | Time until reservation expires |
| `grace_period_ms` | 0 – 60s | 5s | Window after TTL for in-flight commits |
| `extend_by_ms` | 1ms – 24h | *(required)* | Added to current `expires_at_ms` (not request time). Server may clamp to policy limits. |

### Reservation statuses

`ACTIVE` — reserved, awaiting commit/release. `COMMITTED` — actual spend recorded. `RELEASED` — budget returned. `EXPIRED` — TTL elapsed without commit/release.

---

## Operator Guidance

### Monitoring

- Track scopes with `is_over_limit=true` via the `/balances` endpoint.
- Alert at **80%** of `overdraft_limit` (warning) and **100%** (critical).
- Monitor `debt_utilization = debt / overdraft_limit` as a time-series metric.

### Reconciliation runbook

1. Identify which reservations/commits caused the over-limit state.
2. Determine if the overdraft limit should be increased (normal variance) or if this is anomalous consumption (incident).
3. Fund the scope to repay debt below the limit.
4. Verify `is_over_limit` returns to `false`.
5. Operations resume automatically.

---

## Validation

This repository uses [Spectral](https://github.com/stoplightio/spectral) to lint the OpenAPI spec against both standard OpenAPI 3.1 rules and protocol-specific conventions.

```bash
# Install tooling (once)
npm ci

# Run validation
make lint
```

CI runs automatically on pull requests and pushes to `main`. The workflow fails on errors; warnings (e.g., missing schema descriptions) are surfaced but do not block merges.

---

## Non-Goals (v0)

The following are explicitly out of scope for v0:

- Budget establishment and funding operations (create/update/delete budgets)
- Allocation setting, credit/deposit, debit/withdrawal
- Multi-unit atomic reservation/settlement

Implementations may provide these via a separate operator/admin API. Future protocol versions may standardize them.

---

## Evolution Contract

- The API starts at v0.1.0 with `/v1` paths to avoid future client churn.
- v1+ evolution is **backward-compatible by default**: new fields are additive, existing field meanings never change.
- Breaking changes (e.g., new required fields, semantic changes) require a new major API path (e.g., `/v2`).

