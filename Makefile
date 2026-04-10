.PHONY: install lint validate merge clean

SPEC := cycles-protocol-v0.yaml

PROTOCOL_MERGED := merged/cycles-openapi-protocol-merged.yaml
ADMIN_MERGED := merged/cycles-openapi-admin-merged.yaml

## Install validation tooling
install:
	npm ci

## Lint the OpenAPI spec (fails on errors only)
lint: install
	npx spectral lint $(SPEC) --fail-severity=error

## Alias for lint
validate: lint

## Regenerate merged OpenAPI artifacts (protocol plane + admin plane)
merge:
	python scripts/merge_specs.py

## Remove installed dependencies
clean:
	rm -rf node_modules
