# Cycles Protocol — drafts

Pre-normative specs published here for review. **Drafts are not part of the
conformance target** (see [`../CONFORMANCE.md`](../CONFORMANCE.md)) — they
promote to a numbered spec file at the repo root once a production
implementation ships and a cross-system consumer has integrated against them
end-to-end. They are registered in [`../cycles-spec-index.yaml`](../cycles-spec-index.yaml)
as `conformance: reference` (non-normative) with `conformance_status: draft`.

| Draft | What it is |
|---|---|
| [`cycles-aps-denial-mapping-v0.1.md`](cycles-aps-denial-mapping-v0.1.md) | Mapping of Cycles denial reason codes to the APS (agent-passport-system) integration vocabulary. |

> **Graduated:** the **CyclesEvidence envelope** — a JCS-canonicalized (RFC 8785), Ed25519-signed, sha256 content-addressed audit artifact wrapping each authorization lifecycle event, now including normative signer-key authority resolution (did:cycles / JWKS / rotation, formerly tracked in [#103](https://github.com/runcycles/cycles-protocol/issues/103)) — was promoted from this directory to the normative spec [`../cycles-evidence-v0.2.yaml`](../cycles-evidence-v0.2.yaml). Its golden fixtures remain here: [`fixtures/cycles-evidence-v0.1/`](fixtures/cycles-evidence-v0.1/).

## Producing & verifying evidence (where the code lives)

- **`cycles-server`** computes the `evidence_id` content hash *synchronously* and returns the `cycles_evidence` ref on the response; it serves stored envelopes at `GET /v1/evidence/{id}`. It holds only the **public** signer identity.
- **`cycles-server-events`** asynchronously builds, **Ed25519-signs** (the private key lives only here), and stores each envelope; it recomputes the id and dead-letters on producer/worker drift. See its [identity enablement runbook](https://github.com/runcycles/cycles-server-events/blob/main/docs/evidence-identity-enablement.md).
