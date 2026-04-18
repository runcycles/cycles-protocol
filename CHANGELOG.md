# Cycles Protocol — Changelog Index

Each spec in the suite maintains its own changelog. Pick the spec you care
about:

| Spec | Changelog |
|---|---|
| `cycles-protocol-v0.yaml` (runtime base) | [changelogs/cycles-protocol-v0.md](changelogs/cycles-protocol-v0.md) |
| `cycles-governance-admin-v0.1.25.yaml` (governance base) | [changelogs/cycles-governance-admin.md](changelogs/cycles-governance-admin.md) |
| `cycles-action-kinds-v0.1.26.yaml` (action kind registry) | [changelogs/cycles-action-kinds.md](changelogs/cycles-action-kinds.md) |
| `cycles-protocol-extensions-v0.1.26.yaml` (runtime extension) | [changelogs/cycles-protocol-extensions.md](changelogs/cycles-protocol-extensions.md) |
| `cycles-governance-extensions-v0.1.26.yaml` (governance extension) | [changelogs/cycles-governance-extensions.md](changelogs/cycles-governance-extensions.md) |

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
  version: 0.1.25.27
  x-changelog:
    url: ./changelogs/cycles-governance-admin.md
    format: keep-a-changelog
```

Merged artifacts in `merged/` carry an array form, one entry per source spec
that contributed to the merge.
