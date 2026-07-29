# Cycles SDK Recovery Conformance Profile

This profile defines the client-side failure choreography that is intentionally
outside the HTTP server conformance surface in `CONFORMANCE.md`. It gives SDK
authors one shared contract for preserving actual spend, recovering ambiguous
settlement outcomes, and reporting lease-heartbeat failures.

The profile is versioned independently from the wire protocol. Its executable
scenario catalog is [`scenarios.yaml`](scenarios.yaml).

## Scope and guarantee boundary

An SDK can only recover an amount it knows. The durable-settlement requirements
begin when the integration has obtained the actual amount and initiates commit
or direct-event settlement. If a process dies before the downstream operation
returns an actual amount, the SDK MUST NOT claim that the ledger will converge.
Applications that need that stronger guarantee must durably checkpoint provider
receipts or actual usage before acknowledging the downstream operation.

The requirements below apply to lifecycle helpers that own the complete
reserve-execute-commit flow. Low-level clients MAY expose the primitives instead
of automatically scheduling recovery, but MUST document that distinction.

## Recovery levels

### Core recovery

A core-conformant SDK:

- MUST reuse the original idempotency key after a timeout, connection failure,
  5xx response, rate limit, or otherwise ambiguous commit result.
- MUST honor a valid `Retry-After` delay on 429 responses, subject to its
  documented bounded-delay policy.
- MUST stop retrying a genuine, understood client rejection.
- MUST recover an HTTP 410 or `RESERVATION_EXPIRED` commit through
  `POST /v1/events` when it has the original subject, action, actual amount,
  metrics, metadata, and idempotency key.
- MUST NOT release a reservation merely because settlement is ambiguous or
  authentication failed after the guarded action already happened.

### Durable recovery

A durable-conformant SDK additionally:

- MUST persist an unresolved settlement before the first commit or direct-event
  request once actual usage is known. The durable write MUST complete before
  the request can leave the process. If persistence fails, the SDK MUST surface
  the failure to operators but MAY still make the synchronous settlement
  attempt.
- MUST write each record atomically, restrict access to records where the
  platform supports permissions, and quarantine malformed records.
- MUST retain records across retry exhaustion, authentication failure,
  unclassifiable 4xx responses, and process restart.
- MUST remove a record only after schema-valid settlement success or a genuine,
  understood terminal rejection.
- MUST persist the absolute earliest retry time derived from 429 so a restart
  cannot retry earlier than the server allowed.
- MUST change a record from commit mode to event mode before retrying an expired
  reservation through `POST /v1/events`.
- MUST make concurrent replay safe by reusing the stored idempotency key.
- SHOULD partition records by server and principal. If tenant identity is
  configured, the partition SHOULD remain stable across API-key rotation.
- MUST expose an explicit flush/drain operation for graceful shutdown, with a
  bounded wait whose timeout leaves unresolved records intact.
- MUST derive journal filenames from the exact UTF-8 reservation identifier
  with a collision-resistant, cross-language algorithm. The standard filename
  is `v2-<sha256-lower-hex>.json`, where the digest input is the unmodified
  UTF-8 reservation identifier. Implementations upgrading from a legacy
  filename scheme MUST migrate a valid record to the standard filename and
  MUST NOT delete a legacy file unless its stored reservation identifier
  exactly matches the requested identifier.

Durability is best-effort only when journal I/O itself fails. Such a failure MUST
be surfaced to operators and MUST NOT prevent the synchronous settlement attempt.

## Heartbeat failure policy

Heartbeat extension is a lease-safety signal, not settlement. Every SDK MUST
document its policy. The baseline `warn` policy is:

- a transport exception or terminal extend response MUST be observable and MUST
  include the reservation identifier and retry/stop disposition;
- a recoverable failure keeps retrying with the same idempotency key according
  to the runtime spec's heartbeat algorithm;
- heartbeat failure alone does not cancel user work or suppress final commit;
  settlement still runs when actual usage becomes known.

SDKs MAY additionally expose `fail_on_finalize` or `cancel` policies. They MUST
not silently swallow heartbeat failures under any policy.

## Executable scenario contract

`scenarios.yaml` is the shared source of scenario IDs and observable outcomes.
SDK repositories MUST bind every scenario whose `level` they claim to a
native adapter, including child-process tests for restart and concurrent
replay. Core and durable claims both include boundary scenarios. The shared
runner invokes that adapter once per scenario in a fresh process, writes only
the scenario inputs (`id`, `level`, `name`, `precondition`, and `faults`) to
stdin, appends the scenario ID to the adapter command, and requires one JSON
result on stdout:

```json
{
  "scenario_id": "CR-CORE-001",
  "passed": true,
  "observed_requests": ["commit", "commit_same_key"],
  "assertions": [
    "settlement_occurs_at_most_once",
    "retry_uses_original_idempotency_key"
  ]
}
```

Diagnostics belong on stderr. `observed_requests` must exactly match the shared
choreography; `assertions` may contain adapter-specific observations in
addition to every required assertion. The expected request choreography and
required assertions are runner-owned oracle data and are never disclosed to
the adapter. An adapter MUST obtain its observations by executing the SDK's
native behavior test; echoing catalog expectations is not conformance. A
durable SDK runs core, durable, and boundary scenarios:

```sh
python scripts/run_client_recovery_conformance.py \
  --claim durable \
  --adapter path/to/sdk-recovery-adapter
```

The catalog deliberately separates:

- `precondition`: what the SDK can durably know,
- `faults`: injected failures in order,
- `expected_requests`: the allowed settlement choreography, and
- `assertions`: externally observable outcomes.

An SDK claiming durable recovery MUST run the shared runner in CI and publish
a mapping from every durable scenario ID to its adapter test. Merely testing
request serialization does not satisfy this profile.
