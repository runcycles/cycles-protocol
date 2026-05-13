# CyclesEvidence v0.1 — reference fixtures

Thirteen signed, content-addressed `CyclesEvidence` envelopes covering
the five artifact types, the decision branches an audit consumer needs
to handle (including the live-path 4xx denial introduced for the issue
#25 integration, a 403 error on `POST /v1/decide`, and a commit with
`StandardMetrics` populated), and every value of the closed `Unit` enum.
Each fixture is the JCS-canonical bytes of a fully populated envelope,
exactly as a Cycles server would emit it.

These fixtures back the test-plan checkbox on PR
`runcycles/cycles-protocol#90`:

> Implement a worked example: emit one envelope per artifact type from
> a reference Cycles server, compute `evidence_id`, sign, then
> re-verify; commit fixtures alongside the spec.

## Layout

```
generate.py                       — generator (deterministic)
verify.py                         — verifier (round-trip check)
requirements.txt                  — jcs, pynacl
cases/
  01-decide-allow.json                  — DecidePayload, decision=ALLOW
  02-reserve-allow.json                 — ReservePayload, decision=ALLOW, balances populated
  03-reserve-dry-run-deny.json          — ReservePayload with dry_run=true, decision=DENY (the ONLY valid wire shape for decision=DENY on reserve, per cycles-protocol-v0:978)
  04-reserve-allow-with-caps.json       — ReservePayload, decision=ALLOW_WITH_CAPS, Caps populated
  05-commit-success.json                — CommitPayload, reservation_id hoisted, partial commit
  06-release-success.json               — ReleasePayload, ALLOW_WITH_CAPS reservation released
  07-release-with-reason.json           — ReleasePayload with optional ReleaseRequest.reason
  08-reserve-allow-no-trace-id.json     — ReservePayload, optional trace_id omitted (field absent, NOT empty string)
  09-decide-risk-points-allow.json      — DecidePayload, unit=RISK_POINTS (authority class), Action.tags populated
  10-reserve-credits-allow.json         — ReservePayload, unit=CREDITS (implementation-defined class), Balance.allocated populated
  11-reserve-live-budget-exceeded.json  — ErrorPayload, 409 BUDGET_EXCEEDED, endpoint="POST /v1/reservations" — the canonical live-denial wire shape that issue #25's APS gateway needs to bind evidence to
  12-decide-live-forbidden.json         — ErrorPayload, 403 FORBIDDEN, endpoint="POST /v1/decide" — exercises the corrected endpoint name (canonical /v1/decide, not /v1/decisions) and a non-budget ErrorCode
  13-commit-with-metrics.json           — CommitPayload with StandardMetrics populated (5 fields incl. `custom` escape hatch) — exercises the constrained StandardMetrics mirror added in round 6 (object schema with `additionalProperties: false` and per-field constraints; not an enum)
```

## What each fixture proves

| Fixture | Spec rule exercised |
|---|---|
| 01 | `decide` payload one-of branch; `DecisionResponse` minimal-required shape (only `decision`) |
| 02 | `reserve` happy path; `Balance` with `SignedAmount` `remaining` |
| 03 | Dry-run reserve DENY — the *only* legal wire shape with `decision: DENY` on a reserve. Per `cycles-protocol-v0.yaml` §ReservationCreateResponse.decision: "For dry_run=true, decision MAY be DENY. For dry_run=false, insufficient budget MUST be expressed via 409 BUDGET_EXCEEDED (not decision=DENY)." Live (non-dry) denials are case 11. |
| 04 | ALLOW_WITH_CAPS preserves the `Caps` payload in signed bytes (load-bearing for audit per `#25` thread) |
| 05 | `reservation_id` hoisted into the signed payload — closes the `commit_reservation` linkage gap from `#92` review round 4 |
| 06 | `release` payload one-of branch; symmetric `reservation_id` hoist |
| 07 | Optional `ReleaseRequest.reason` round-trips through canonical bytes |
| 08 | Optional `trace_id` **omitted** (field absent in canonical bytes — distinct from `""` or `null` per spec normative note on omit/null/empty) |
| 09 | `RISK_POINTS` unit (authority class per `#25` `unit_class` discussion); optional `Action.tags` populated |
| 10 | `CREDITS` unit (implementation-defined class per `cycles-protocol-v0` UnitEnum); optional `Balance.allocated` populated |
| 11 | `error` artifact type — live (non-dry) 409 `BUDGET_EXCEEDED` from `POST /v1/reservations`. The canonical wire shape for the pre-execution denial path that issue #25 needs APS receipts to bind evidence to. The request body is preserved in the signed payload; `endpoint` discriminates which Mirror schema `request` follows. |
| 12 | `error` artifact type — 403 `FORBIDDEN` from `POST /v1/decide` (canonical endpoint name, not `/v1/decisions`). Exercises the decide error path and a non-budget ErrorCode value (the round-5 fix renamed the endpoint everywhere; this fixture proves the endpoint-discriminated request validation accepts a real `DecisionRequest` body under the correct endpoint name). |
| 13 | `commit` artifact type with `metrics` populated. Exercises the `StandardMetrics` mirror added in round 6: all five canonical fields (`tokens_input`, `tokens_output`, `latency_ms`, `model_version`, `custom`) with the `custom` escape hatch carrying deployment-specific extras. Closes the coverage gap that allowed `CommitRequestMirror.metrics` to be `additionalProperties: true` undetected. |

## Reproducing the fixtures

```sh
pip install -r requirements.txt
python generate.py
```

The generator is deterministic. Re-running it overwrites `cases/*.json`
with byte-identical output; a clean working tree after `python
generate.py` proves the fixtures match the spec algorithm.

## Verifying the fixtures

```sh
python verify.py
```

For each fixture, `verify.py` runs the v0.1 normative verification
contract from `cycles-evidence-v0.1.yaml`:

1. Recompute `evidence_id` (sha256 over JCS-canonical bytes with
   `evidence_id=""` and `signature=""`); compare byte-for-byte.
2. Recanonicalize with `evidence_id` populated and `signature=""`;
   Ed25519-verify against the pubkey resolved from `signer_did`.
3. Check `artifact_type` matches exactly one `payload` key.
4. Validate optional `trace_id` against the 32-hex pattern when
   present.

Exit code 0 on all-green; non-zero on any failure.

## Test signer

**These fixtures are signed with a test key. They are NOT authoritative
evidence and the keypair MUST NOT be used by any production
deployment.**

The signer seed is derived deterministically as:

```
sha256("cycles-evidence-v0.1-fixture-signer")
```

so anyone can re-derive the same Ed25519 keypair locally. The resulting
public key (which appears as `signer_did` in every fixture) is:

```
ec52b49b81eb29ef6f62947cade245c715bf943b7ef2a5f2789288574466fc43
```

Production Cycles deployments will sign with a server-owned key
published via the `did:cycles:*` method (out of scope for v0.1, see
spec).

## Spot-checking tamper detection

Flip one character anywhere in a fixture's signed bytes (the payload,
the timestamp, the trace_id) and re-run `verify.py`. The verifier
reports both `evidence_id mismatch` and `signature verification
failed`. This demonstrates that the canonical-bytes input to sha256
covers the whole envelope and that the Ed25519 signature is tied to
the recomputed `evidence_id`.

Example:

```sh
# Tamper: change reservation_id one byte
python -c "
import json, pathlib
p = pathlib.Path('cases/05-commit-success.json')
e = json.loads(p.read_text())
e['payload']['commit']['reservation_id'] = e['payload']['commit']['reservation_id'][:-1] + 'X'
p.write_text(json.dumps(e))
"
python verify.py   # → FAIL on 05-commit-success.json
python generate.py # → restores from canonical sources
```

## Promoting these fixtures

When `cycles-evidence-v0.1.yaml` graduates from `drafts/` to a numbered
spec at repo root, this fixture set should move with it (e.g. to
`fixtures/cycles-evidence-v0.2/`). The generator inputs in
`generate.py` should be reviewed at promotion time and any sample IDs
/ public-key references regenerated against the production signing-key
shape once `did:cycles:*` is normative.
