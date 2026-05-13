"""Generate signed CyclesEvidence v0.1 fixtures.

Run from this directory:

    pip install -r requirements.txt
    python generate.py

Writes one JSON file per case under ./cases/.

The signer is a TEST KEY ONLY, derived deterministically so the generator
is reproducible and reviewers can re-verify fixtures byte-for-byte. The
seed is sha256("cycles-evidence-v0.1-fixture-signer"); the same input
produces the same Ed25519 keypair on every run.

Implements the v0.1 normative algorithm from
drafts/cycles-evidence-v0.1.yaml:

    1. Build envelope with evidence_id="" and signature="" (empty-string
       sentinel — NOT field omission, NOT JSON null).
    2. JCS-canonicalize, sha256 → evidence_id (hex).
    3. Populate evidence_id, keep signature="", JCS-canonicalize again,
       Ed25519-sign → signature (hex).
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import jcs
import nacl.signing


FIXTURE_SIGNER_LABEL = "cycles-evidence-v0.1-fixture-signer"


def derive_signer() -> nacl.signing.SigningKey:
    seed = sha256(FIXTURE_SIGNER_LABEL.encode("utf-8")).digest()
    return nacl.signing.SigningKey(seed)


def sign_envelope(envelope: dict, signer: nacl.signing.SigningKey) -> dict:
    if "evidence_id" in envelope or "signature" in envelope:
        raise ValueError("caller must omit evidence_id/signature; generator sets them")

    pre_hash = {**envelope, "evidence_id": "", "signature": ""}
    evidence_id = sha256(jcs.canonicalize(pre_hash)).hexdigest()

    pre_sign = {**envelope, "evidence_id": evidence_id, "signature": ""}
    signature = signer.sign(jcs.canonicalize(pre_sign)).signature.hex()

    return {**envelope, "evidence_id": evidence_id, "signature": signature}


SIGNER_DID = derive_signer().verify_key.encode().hex()
SERVER_ID = "https://cycles.example.com/v1"
SCHEMA_VERSION = "cycles-evidence/v0.1"


def base(artifact_type: str, issued_at_ms: int, trace_id: str | None, payload: dict) -> dict:
    env: dict = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": artifact_type,
        "server_id": SERVER_ID,
        "signer_did": SIGNER_DID,
        "issued_at_ms": issued_at_ms,
    }
    if trace_id is not None:
        env["trace_id"] = trace_id
    env["payload"] = payload
    return env


def case_01_decide_allow() -> dict:
    return base(
        "decide",
        1810000000000,
        "0af7651916cd43dd8448eb211c80319c",
        {
            "decide": {
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0A1",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {"kind": "model.call", "name": "gpt-4o"},
                    "estimate": {"unit": "USD_MICROCENTS", "amount": 2000000},
                },
                "response": {
                    "decision": "ALLOW",
                    "affected_scopes": ["tenant"],
                },
            },
        },
    )


def case_02_reserve_allow() -> dict:
    return base(
        "reserve",
        1810000000100,
        "0af7651916cd43dd8448eb211c80319c",
        {
            "reserve": {
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0A2",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {"kind": "model.call", "name": "gpt-4o"},
                    "estimate": {"unit": "USD_MICROCENTS", "amount": 2000000},
                    "ttl_ms": 30000,
                },
                "response": {
                    "decision": "ALLOW",
                    "reservation_id": "rsv_01HZZ8N4F8FBQX5K6TGYR0M0A3",
                    "reserved": {"unit": "USD_MICROCENTS", "amount": 2000000},
                    "affected_scopes": ["tenant"],
                    "expires_at_ms": 1810000030100,
                    "scope_path": "tenant=acme",
                    "balances": [
                        {
                            "scope": "tenant",
                            "scope_path": "tenant=acme",
                            "remaining": {"unit": "USD_MICROCENTS", "amount": 8000000},
                            "reserved": {"unit": "USD_MICROCENTS", "amount": 2000000},
                            "spent": {"unit": "USD_MICROCENTS", "amount": 0},
                        },
                    ],
                },
            },
        },
    )


def case_03_reserve_dry_run_deny() -> dict:
    # decision: DENY on a reserve is only valid on dry_run=true per
    # cycles-protocol-v0.yaml §ReservationCreateResponse.decision:
    # "For dry_run=true, decision MAY be DENY. For dry_run=false,
    # insufficient budget MUST be expressed via 409 BUDGET_EXCEEDED
    # (not decision=DENY)."
    # Live (non-dry) budget denials are captured by case_11 via the
    # `error` artifact type.
    return base(
        "reserve",
        1810000000200,
        "b9c8a0d3f2e147a9a7f4d2e1b0c9876f",
        {
            "reserve": {
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0B1",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {"kind": "model.call", "name": "gpt-4o"},
                    "estimate": {"unit": "USD_MICROCENTS", "amount": 50000000},
                    "ttl_ms": 30000,
                    "dry_run": True,
                },
                "response": {
                    "decision": "DENY",
                    "affected_scopes": ["tenant"],
                    "reason_code": "BUDGET_EXCEEDED",
                    "scope_path": "tenant=acme",
                    "balances": [
                        {
                            "scope": "tenant",
                            "scope_path": "tenant=acme",
                            "remaining": {"unit": "USD_MICROCENTS", "amount": 8000000},
                            "reserved": {"unit": "USD_MICROCENTS", "amount": 0},
                            "spent": {"unit": "USD_MICROCENTS", "amount": 92000000},
                        },
                    ],
                },
            },
        },
    )


def case_04_reserve_allow_with_caps() -> dict:
    return base(
        "reserve",
        1810000000300,
        "c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
        {
            "reserve": {
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0C1",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {"kind": "model.call", "name": "gpt-4o"},
                    "estimate": {"unit": "TOKENS", "amount": 32000},
                    "ttl_ms": 30000,
                },
                "response": {
                    "decision": "ALLOW_WITH_CAPS",
                    "reservation_id": "rsv_01HZZ8N4F8FBQX5K6TGYR0M0C2",
                    "reserved": {"unit": "TOKENS", "amount": 8000},
                    "affected_scopes": ["tenant"],
                    "expires_at_ms": 1810000030300,
                    "caps": {
                        "max_tokens": 8000,
                        "tool_allowlist": ["read.*"],
                        "cooldown_ms": 1000,
                    },
                    "scope_path": "tenant=acme",
                },
            },
        },
    )


def case_05_commit_success() -> dict:
    return base(
        "commit",
        1810000010000,
        "0af7651916cd43dd8448eb211c80319c",
        {
            "commit": {
                "reservation_id": "rsv_01HZZ8N4F8FBQX5K6TGYR0M0A3",
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0A4",
                    "actual": {"unit": "USD_MICROCENTS", "amount": 1750000},
                },
                "response": {
                    "status": "COMMITTED",
                    "charged": {"unit": "USD_MICROCENTS", "amount": 1750000},
                    "released": {"unit": "USD_MICROCENTS", "amount": 250000},
                    "balances": [
                        {
                            "scope": "tenant",
                            "scope_path": "tenant=acme",
                            "remaining": {"unit": "USD_MICROCENTS", "amount": 8250000},
                            "reserved": {"unit": "USD_MICROCENTS", "amount": 0},
                            "spent": {"unit": "USD_MICROCENTS", "amount": 1750000},
                        },
                    ],
                },
            },
        },
    )


def case_06_release_success() -> dict:
    return base(
        "release",
        1810000005000,
        "d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6",
        {
            "release": {
                "reservation_id": "rsv_01HZZ8N4F8FBQX5K6TGYR0M0C2",
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0C3",
                },
                "response": {
                    "status": "RELEASED",
                    "released": {"unit": "TOKENS", "amount": 8000},
                    "balances": [
                        {
                            "scope": "tenant",
                            "scope_path": "tenant=acme",
                            "remaining": {"unit": "TOKENS", "amount": 100000},
                            "reserved": {"unit": "TOKENS", "amount": 0},
                            "spent": {"unit": "TOKENS", "amount": 0},
                        },
                    ],
                },
            },
        },
    )


def case_07_release_with_reason() -> dict:
    return base(
        "release",
        1810000007000,
        "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6",
        {
            "release": {
                "reservation_id": "rsv_01HZZ8N4F8FBQX5K6TGYR0M0A3",
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0A5",
                    "reason": "handler_timeout",
                },
                "response": {
                    "status": "RELEASED",
                    "released": {"unit": "USD_MICROCENTS", "amount": 2000000},
                    "balances": [
                        {
                            "scope": "tenant",
                            "scope_path": "tenant=acme",
                            "remaining": {"unit": "USD_MICROCENTS", "amount": 10000000},
                            "reserved": {"unit": "USD_MICROCENTS", "amount": 0},
                            "spent": {"unit": "USD_MICROCENTS", "amount": 0},
                        },
                    ],
                },
            },
        },
    )


def case_09_decide_risk_points_allow() -> dict:
    # RISK_POINTS is the authority-class unit per the unit_class discussion
    # on aeoess/agent-passport-system#25 — non-monetary action-authority
    # budget keyed against an ActionRiskClass taxonomy. This fixture
    # exercises a pre-execution decide for a side-effecting action with a
    # RISK_POINTS estimate, returning ALLOW.
    return base(
        "decide",
        1810000020000,
        "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
        {
            "decide": {
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0E1",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {
                        "kind": "tool.call",
                        "name": "send_external_email",
                        "tags": ["prod", "customer-facing"],
                    },
                    "estimate": {"unit": "RISK_POINTS", "amount": 5},
                },
                "response": {
                    "decision": "ALLOW",
                    "affected_scopes": ["tenant", "agent"],
                },
            },
        },
    )


def case_10_reserve_credits_allow() -> dict:
    # CREDITS is described in cycles-protocol-v0.yaml UnitEnum as a
    # "generic integer unit (optional in v0 implementations)". This
    # fixture exercises only the Cycles wire surface: CREDITS as a
    # closed-enum unit name preserved byte-for-byte through the
    # signed envelope.
    #
    # Whether CREDITS maps to APS unit_class=consumption,
    # =authority, or =implementation-defined is an APS receipt
    # concern tracked on aeoess/agent-passport-system#25, not a
    # CyclesEvidence concern. This envelope makes no claim about
    # APS unit_class; adapter authors writing APS receipts MUST
    # consult the issue #25 thread (and the eventual
    # `crosswalk/cycles.yaml` row at
    # aeoess/agent-governance-vocabulary#92) for the authoritative
    # APS-side mapping rule.
    return base(
        "reserve",
        1810000030000,
        "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        {
            "reserve": {
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0F1",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {"kind": "compute.job", "name": "image-render"},
                    "estimate": {"unit": "CREDITS", "amount": 50},
                    "ttl_ms": 60000,
                },
                "response": {
                    "decision": "ALLOW",
                    "reservation_id": "rsv_01HZZ8N4F8FBQX5K6TGYR0M0F2",
                    "reserved": {"unit": "CREDITS", "amount": 50},
                    "affected_scopes": ["tenant"],
                    "expires_at_ms": 1810000090000,
                    "scope_path": "tenant=acme",
                    "balances": [
                        {
                            "scope": "tenant",
                            "scope_path": "tenant=acme",
                            "remaining": {"unit": "CREDITS", "amount": 950},
                            "reserved": {"unit": "CREDITS", "amount": 50},
                            "spent": {"unit": "CREDITS", "amount": 0},
                            "allocated": {"unit": "CREDITS", "amount": 1000},
                        },
                    ],
                },
            },
        },
    )


def case_08_reserve_allow_no_trace_id() -> dict:
    return base(
        "reserve",
        1810000000400,
        None,
        {
            "reserve": {
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0D1",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {"kind": "model.call", "name": "gpt-4o"},
                    "estimate": {"unit": "USD_MICROCENTS", "amount": 1000000},
                    "ttl_ms": 30000,
                },
                "response": {
                    "decision": "ALLOW",
                    "reservation_id": "rsv_01HZZ8N4F8FBQX5K6TGYR0M0D2",
                    "reserved": {"unit": "USD_MICROCENTS", "amount": 1000000},
                    "affected_scopes": ["tenant"],
                    "expires_at_ms": 1810000030400,
                },
            },
        },
    )


def case_13_commit_with_metrics() -> dict:
    # Exercises StandardMetrics on CommitRequest. Closes the coverage
    # gap that hid the round-6 finding (CommitRequestMirror.metrics
    # was an arbitrary object instead of referencing StandardMetrics).
    # Carries all five canonical StandardMetrics fields including the
    # `custom` escape hatch.
    return base(
        "commit",
        1810000060000,
        "abcdef0123456789abcdef0123456789",
        {
            "commit": {
                "reservation_id": "rsv_01HZZ8N4F8FBQX5K6TGYR0M0J1",
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0J2",
                    "actual": {"unit": "USD_MICROCENTS", "amount": 1500000},
                    "metrics": {
                        "tokens_input": 1500,
                        "tokens_output": 800,
                        "latency_ms": 2340,
                        "model_version": "claude-sonnet-4-20250514",
                        "custom": {
                            "cache_hit_ratio": 0.42,
                            "retry_count": 0,
                        },
                    },
                    "metadata": {"workflow_run_id": "wf_abc123"},
                },
                "response": {
                    "status": "COMMITTED",
                    "charged": {"unit": "USD_MICROCENTS", "amount": 1500000},
                    "balances": [
                        {
                            "scope": "tenant",
                            "scope_path": "tenant=acme",
                            "remaining": {"unit": "USD_MICROCENTS", "amount": 8500000},
                            "reserved": {"unit": "USD_MICROCENTS", "amount": 0},
                            "spent": {"unit": "USD_MICROCENTS", "amount": 1500000},
                        },
                    ],
                },
            },
        },
    )


def case_12_decide_live_forbidden() -> dict:
    # Live 4xx error on POST /v1/decide. Exercises the corrected
    # endpoint name (canonical is /v1/decide, not /v1/decisions; the
    # earlier draft had this wrong and no fixture caught it because
    # no error fixture used the decide endpoint).
    return base(
        "error",
        1810000050000,
        "fedcba9876543210fedcba9876543210",
        {
            "error": {
                "endpoint": "POST /v1/decide",
                "http_status": 403,
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0H1",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {"kind": "model.call", "name": "gpt-4o"},
                    "estimate": {"unit": "USD_MICROCENTS", "amount": 1000000},
                },
                "response": {
                    "error": "FORBIDDEN",
                    "message": "Tenant scope mismatch with effective auth context",
                    "request_id": "req_01HZZ8N4F8FBQX5K6TGYR0M0H2",
                    "trace_id": "fedcba9876543210fedcba9876543210",
                },
            },
        },
    )


def case_11_reserve_live_budget_exceeded() -> dict:
    # Non-dry reserve over budget: the canonical wire shape is a 409
    # ErrorResponse with error: BUDGET_EXCEEDED, NOT a 200 with
    # decision: DENY (see cycles-protocol-v0.yaml:978). Captured here
    # via the `error` artifact type with endpoint
    # "POST /v1/reservations". This is the live denial path
    # referenced in aeoess/agent-passport-system#25 ("Cycles denies
    # → APS blocks/audits") — without an error-artifact slot, v0.1
    # would have no evidence for the most important denial branch.
    return base(
        "error",
        1810000040000,
        "0123456789abcdef0123456789abcdef",
        {
            "error": {
                "endpoint": "POST /v1/reservations",
                "http_status": 409,
                "request": {
                    "idempotency_key": "01HZZ8N4F8FBQX5K6TGYR0M0G1",
                    "subject": {"tenant": "acme", "agent": "researcher"},
                    "action": {"kind": "model.call", "name": "gpt-4o"},
                    "estimate": {"unit": "USD_MICROCENTS", "amount": 100000000},
                    "ttl_ms": 30000,
                },
                "response": {
                    "error": "BUDGET_EXCEEDED",
                    "message": "Insufficient remaining budget for scope tenant=acme",
                    "request_id": "req_01HZZ8N4F8FBQX5K6TGYR0M0G2",
                    "trace_id": "0123456789abcdef0123456789abcdef",
                },
            },
        },
    )


CASES: list[tuple[str, dict]] = [
    ("01-decide-allow.json", case_01_decide_allow()),
    ("02-reserve-allow.json", case_02_reserve_allow()),
    ("03-reserve-dry-run-deny.json", case_03_reserve_dry_run_deny()),
    ("04-reserve-allow-with-caps.json", case_04_reserve_allow_with_caps()),
    ("05-commit-success.json", case_05_commit_success()),
    ("06-release-success.json", case_06_release_success()),
    ("07-release-with-reason.json", case_07_release_with_reason()),
    ("08-reserve-allow-no-trace-id.json", case_08_reserve_allow_no_trace_id()),
    ("09-decide-risk-points-allow.json", case_09_decide_risk_points_allow()),
    ("10-reserve-credits-allow.json", case_10_reserve_credits_allow()),
    ("11-reserve-live-budget-exceeded.json", case_11_reserve_live_budget_exceeded()),
    ("12-decide-live-forbidden.json", case_12_decide_live_forbidden()),
    ("13-commit-with-metrics.json", case_13_commit_with_metrics()),
]


def main() -> None:
    signer = derive_signer()
    out_dir = Path(__file__).parent / "cases"
    out_dir.mkdir(exist_ok=True)

    expected = {filename for filename, _ in CASES}
    for stale in sorted(out_dir.glob("*.json")):
        if stale.name not in expected:
            stale.unlink()
            print(f"removed stale {stale.name}")

    for filename, raw in CASES:
        signed = sign_envelope(raw, signer)
        canonical = jcs.canonicalize(signed)
        (out_dir / filename).write_bytes(canonical + b"\n")
        print(f"wrote {filename} ({len(canonical)} canonical bytes)")

    print(f"\nsigner pubkey (hex): {SIGNER_DID}")
    print(f"signer label:        {FIXTURE_SIGNER_LABEL}")


if __name__ == "__main__":
    main()
