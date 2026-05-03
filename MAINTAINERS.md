# Maintainers

This document lists the people responsible for triaging issues, reviewing PRs, and cutting releases for `cycles-protocol` (the OpenAPI 3.1 specification that defines the Cycles authority API contract — the source of truth every server and client implementation derives from).

## Project lead

- **Albert Mavashev** — [@amavashev](https://github.com/amavashev) — primary committer, release manager

## Contributing organizations

The project receives contributions from:

- [Runcycles](https://github.com/runcycles)
- [K2NIO](https://github.com/K2NIO)
- Singleton Labs

## Responsibilities

| Area | Owner | SLA |
|---|---|---|
| Issue triage | Project lead | 5 business days for first response |
| PR review | Project lead | 3 business days for initial review (extra-conservative — spec changes propagate to every implementation) |
| Security disclosures | See [SECURITY.md](https://github.com/runcycles/.github/blob/main/SECURITY.md) | 48h acknowledgment, 5 business days assessment |
| Spec versioning | Project lead | Patch bumps for clarification fixes; minor for additive changes; major for breaking. Pre-1.0: discipline maintained but no SemVer guarantee yet |
| Release cuts | Project lead | Per-tag; downstream implementations pin to spec versions in their builds |
| Dependency updates | Dependabot + project lead | Auto-merge on patch updates passing validation; manual review on minor/major |

## Becoming a maintainer

We're a small team and add maintainers cautiously. Path is usually: sustained contribution (≥3 substantive PRs) → triage assistance → invitation to commit access. Open a discussion if you're interested.

**Note on spec changes**: PRs that propose breaking or semantic changes to the protocol require explicit acknowledgment of impact on `cycles-server` (reference impl) and the four client SDKs (`cycles-client-python`, `cycles-client-typescript`, `cycles-client-rust`, `cycles-spring-boot-starter`).

## How to reach maintainers

- **General questions / bug reports**: [GitHub Issues](https://github.com/runcycles/cycles-protocol/issues)
- **Security disclosures**: see [SECURITY.md](https://github.com/runcycles/.github/blob/main/SECURITY.md) (do **not** open a public issue)
- **Conduct concerns**: see the org-wide [Code of Conduct](https://github.com/runcycles/.github/blob/main/CODE_OF_CONDUCT.md)
