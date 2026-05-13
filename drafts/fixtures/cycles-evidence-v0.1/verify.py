"""Verify CyclesEvidence v0.1 fixtures.

Run from this directory:

    pip install -r requirements.txt
    python verify.py

Runs the normative verification path from
drafts/cycles-evidence-v0.1.yaml against every fixture under ./cases/:

    1. Reject any envelope whose schema_version is not understood
       (spec MUST on `schema_version`).
    2. Re-derive evidence_id (sha256 over JCS-canonical bytes with
       evidence_id="" and signature="") and compare byte-for-byte.
    3. Re-canonicalize with evidence_id populated and signature="",
       Ed25519-verify the signature against the pubkey resolved from
       signer_did.
    4. Check artifact_type ↔ payload key consistency (the v0.1 spec
       MUST: "artifact_type: commit REQUIRES payload.commit and forbids
       the others", etc.).
    5. Check optional trace_id matches the 32-hex W3C Trace Context
       pattern when present.

Exit code 0 = all green. Non-zero = at least one fixture failed; the
failure mode is printed per fixture.
"""

from __future__ import annotations

import json
import re
import sys
from hashlib import sha256
from pathlib import Path

import jcs
import nacl.exceptions
import nacl.signing


SCHEMA_VERSION = "cycles-evidence/v0.1"
ARTIFACT_TYPES = ("decide", "reserve", "commit", "release", "error")
TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
EVIDENCE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")


def verify_envelope(envelope: dict) -> list[str]:
    errors: list[str] = []

    schema_version = envelope.get("schema_version")
    evidence_id = envelope.get("evidence_id")
    signature = envelope.get("signature")
    signer_did = envelope.get("signer_did")
    artifact_type = envelope.get("artifact_type")
    payload = envelope.get("payload")
    trace_id = envelope.get("trace_id")

    if schema_version != SCHEMA_VERSION:
        errors.append(
            f"schema_version not understood: expected {SCHEMA_VERSION!r}, got {schema_version!r}"
        )
        return errors

    if not isinstance(evidence_id, str) or not EVIDENCE_ID_RE.match(evidence_id):
        errors.append(f"evidence_id missing or not 64-hex: {evidence_id!r}")
        return errors
    if not isinstance(signature, str) or not SIGNATURE_RE.match(signature):
        errors.append(f"signature missing or not 128-hex: {signature!r}")
        return errors
    if not isinstance(signer_did, str):
        errors.append("signer_did missing")
        return errors

    pre_hash = {**envelope, "evidence_id": "", "signature": ""}
    recomputed_id = sha256(jcs.canonicalize(pre_hash)).hexdigest()
    if recomputed_id != evidence_id:
        errors.append(
            f"evidence_id mismatch: envelope={evidence_id}, recomputed={recomputed_id}"
        )

    pre_sign = {**envelope, "signature": ""}
    canonical_signed = jcs.canonicalize(pre_sign)
    try:
        verify_key = nacl.signing.VerifyKey(bytes.fromhex(signer_did))
        verify_key.verify(canonical_signed, bytes.fromhex(signature))
    except (ValueError, nacl.exceptions.BadSignatureError) as exc:
        errors.append(f"signature verification failed: {exc}")

    if artifact_type not in ARTIFACT_TYPES:
        errors.append(f"artifact_type not in {ARTIFACT_TYPES}: {artifact_type!r}")
    elif not isinstance(payload, dict):
        errors.append("payload missing or not an object")
    else:
        present = [k for k in ARTIFACT_TYPES if k in payload]
        if present != [artifact_type]:
            errors.append(
                f"payload keys {present!r} do not match artifact_type {artifact_type!r}"
            )

    if trace_id is not None and not (isinstance(trace_id, str) and TRACE_ID_RE.match(trace_id)):
        errors.append(f"trace_id present but not 32-hex: {trace_id!r}")

    return errors


def main() -> int:
    cases_dir = Path(__file__).parent / "cases"
    fixtures = sorted(cases_dir.glob("*.json"))
    if not fixtures:
        print(f"no fixtures found under {cases_dir}", file=sys.stderr)
        return 2

    failures = 0
    for path in fixtures:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        errors = verify_envelope(envelope)
        if errors:
            failures += 1
            print(f"FAIL  {path.name}")
            for err in errors:
                print(f"      - {err}")
        else:
            print(f"OK    {path.name}  evidence_id={envelope['evidence_id'][:16]}…")

    print()
    print(f"{len(fixtures) - failures}/{len(fixtures)} fixtures verified")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
