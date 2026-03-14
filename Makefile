.PHONY: install lint validate clean

SPEC := cycles-protocol-v0.yaml

## Install validation tooling
install:
	npm ci

## Lint the OpenAPI spec (fails on errors only)
lint: install
	npx spectral lint $(SPEC) --fail-severity=error

## Alias for lint
validate: lint

## Remove installed dependencies
clean:
	rm -rf node_modules
