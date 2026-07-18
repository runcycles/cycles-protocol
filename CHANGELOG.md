# Cycles Protocol — Changelog Index

Each spec in the suite maintains its own changelog. Pick the spec you care
about:

## Repository maintenance — 2026-07-18

- Reconciled both `cycles-spec-index.yaml` runtime version pins with the
  authoritative `cycles-protocol-v0.yaml` `info.version` (`0.1.25.15`) and
  refreshed the associated revision annotations without changing any spec.
- Added `make spec-index-check` to compare every indexed document version and
  current-version summary pin with the referenced spec's `info.version`, and
  wired the check into the OpenAPI validation workflow so future drift fails CI.
- Added `cycles-evidence-v0.2.yaml` to the canonical publication summary and
  the spec changelog index so both inventories cover every indexed companion,
  and extended `make spec-index-check` to prevent the publication summary from
  drifting away from `documents` again.

## Spec changelogs

| Spec | Changelog |
|---|---|
| `cycles-protocol-v0.yaml` (runtime base) | [changelogs/cycles-protocol-v0.md](changelogs/cycles-protocol-v0.md) |
| `cycles-governance-admin-v0.1.25.yaml` (governance base) | [changelogs/cycles-governance-admin.md](changelogs/cycles-governance-admin.md) |
| `cycles-action-kinds-v0.1.26.yaml` (action kind registry) | [changelogs/cycles-action-kinds.md](changelogs/cycles-action-kinds.md) |
| `cycles-protocol-extensions-v0.1.26.yaml` (runtime extension) | [changelogs/cycles-protocol-extensions.md](changelogs/cycles-protocol-extensions.md) |
| `cycles-governance-extensions-v0.1.26.yaml` (governance extension) | [changelogs/cycles-governance-extensions.md](changelogs/cycles-governance-extensions.md) |
| `cycles-evidence-v0.2.yaml` (evidence envelope) | [changelogs/cycles-evidence-v0.2.md](changelogs/cycles-evidence-v0.2.md) |

## Format

Each per-spec changelog follows [Keep a Changelog](https://keepachangelog.com/),
most recent first. The structure is:

```markdown
## v<version> — <YYYY-MM-DD>

- bullet describing the change…
```

Each `## v<version>` heading must match the spec's `info.version` at the time
of the release. CI enforces this with `make changelog-check`
(see `scripts/validate_changelogs.py`).

## Adding an entry

1. Bump `info.version` in the source YAML.
2. Prepend a new `## v<version> — <YYYY-MM-DD>` block to the matching file
   under `changelogs/`. Reuse the prose from your commit message body.
3. Commit. CI will fail if the version on the spec and the latest changelog
   heading don't match.

## Discoverability from the spec

Each source spec carries an OpenAPI vendor extension at `info.x-changelog`:

```yaml
info:
  version: 0.1.25.29
  x-changelog:
    url: ./changelogs/cycles-governance-admin.md
    format: keep-a-changelog
```

Merged artifacts in `merged/` carry an array form, one entry per source spec
that contributed to the merge.
