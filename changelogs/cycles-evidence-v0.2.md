# cycles-evidence — Changelog

Keep-a-Changelog format. Most recent first. Each entry corresponds to an `info.version` bump in `cycles-evidence-v0.2.yaml` (formerly `drafts/cycles-evidence-v0.1.yaml`).

New entries are added directly to this file. See `scripts/validate_changelogs.py` for the CI check that keeps this in sync with the spec.

---

## v0.2.0 — 2026-06-24

_(normative cut — promote the CyclesEvidence envelope from `drafts/` to a numbered spec at repo root)_

- Promotes `drafts/cycles-evidence-v0.1.yaml` to `cycles-evidence-v0.2.yaml`
  at the repo root and makes it NORMATIVE. Promotion gate: the Cycles server
  emits CyclesEvidence envelopes and serves the signer JWK Set
  (`getEvidenceJwks`), AND a cross-system consumer integrates against the
  envelope shape — including signer-key authority resolution — end to end.
  That consumer integration is APS's verify-path wiring in
  aeoess/agent-passport-system#47; this cut lands on that PR's merge.
- Makes the signer-key authority-resolution layer NORMATIVE: the
  `did:cycles:<sha256(server_id)>#<kid>` form of `signer_did`, the
  `CyclesEvidenceJwks` / `CyclesEvidenceJwk` key set served at the
  `server_id`-relative `/.well-known/cycles-jwks.json`, the window-bound
  deterministic key selection (`cycles_nbf_ms` / `cycles_exp_ms`), the
  raw-hex ↔ JWK bridge, and the five DISTINCT verification dispositions
  (`authentic` / `binding_only` / `signer_authority_failed` /
  `signer_resolution_failed` / `signature_invalid`). Previously specified as
  an additive draft layer (cycles-protocol#103).
- The envelope WIRE shape is UNCHANGED. The `schema_version` discriminator
  stays `cycles-evidence/v0.1`; v0.1 envelopes (and the 13 golden fixtures)
  remain valid byte-for-byte. v0.2 is an editorial revision of the document,
  not a wire-breaking change — a verifier that does no resolution still
  yields `binding_only` against an unchanged v0.1 envelope.
- Adds this changelog (`info.x-changelog` now points at
  `./changelogs/cycles-evidence-v0.2.md`).

### Provenance (pre-promotion, under `drafts/cycles-evidence-v0.1.yaml`)

The envelope shape, the JCS (RFC 8785) + sha256 content-hash recipe, the
empty-string-sentinel `evidence_id` / `signature` derivation, the per-artifact
payloads (decide / reserve / commit / release / error), and the response
mirrors were developed and reviewed as the `cycles-evidence/v0.1` draft
(runcycles/cycles-protocol#90). The signer-key resolution layer was added to
that draft and design-agreed with APS on cycles-protocol#103 / #112 before
this normative cut.
