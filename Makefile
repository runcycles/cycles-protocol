.PHONY: install lint lint-sources lint-merged lint-all validate merge merge-check changelog-check clean

# Canonical source specs — all linted in CI.
SOURCE_SPECS := \
	cycles-protocol-v0.yaml \
	cycles-governance-admin-v0.1.25.yaml \
	cycles-action-kinds-v0.1.26.yaml \
	cycles-protocol-extensions-v0.1.26.yaml \
	cycles-governance-extensions-v0.1.26.yaml

PROTOCOL_MERGED := merged/cycles-openapi-protocol-merged.yaml
ADMIN_MERGED := merged/cycles-openapi-admin-merged.yaml

MERGED_SPECS := $(PROTOCOL_MERGED) $(ADMIN_MERGED)

## Install validation tooling
install:
	npm ci

## Lint all canonical source specs (fails on errors only)
lint-sources: install
	@for spec in $(SOURCE_SPECS); do \
		echo ">> Linting $$spec"; \
		npx spectral lint $$spec --fail-severity=error || exit 1; \
	done

## Lint pre-built merged artifacts (catches merge-script bugs that produce invalid OpenAPI)
lint-merged: install
	@for spec in $(MERGED_SPECS); do \
		echo ">> Linting $$spec"; \
		npx spectral lint $$spec --fail-severity=error || exit 1; \
	done

## Lint everything (sources + merged)
lint-all: lint-sources lint-merged

## Legacy alias — lint the runtime base only. Use lint-all in CI.
lint: install
	npx spectral lint cycles-protocol-v0.yaml --fail-severity=error

## Alias for full validation
validate: lint-all merge-check changelog-check

## Verify each source spec's info.x-changelog points at an existing changelog
## file and the latest version heading matches info.version.
changelog-check:
	python scripts/validate_changelogs.py

## Regenerate merged OpenAPI artifacts (protocol plane + admin plane)
merge:
	python scripts/merge_specs.py

## Verify committed merged artifacts match a fresh merge (idempotency / drift check).
## Fails CI if a contributor modified a source spec without running `make merge`.
merge-check:
	python scripts/merge_specs.py
	@if ! git diff --exit-code --quiet merged/; then \
		echo ""; \
		echo "ERROR: Committed merged artifacts are out of date."; \
		echo "A source spec was modified without running 'make merge'."; \
		echo ""; \
		echo "Diff:"; \
		git --no-pager diff merged/; \
		echo ""; \
		echo "To fix: run 'make merge' locally, commit the regenerated files."; \
		exit 1; \
	fi
	@echo ">> Merge drift check passed: committed artifacts match sources."

## Remove installed dependencies
clean:
	rm -rf node_modules
