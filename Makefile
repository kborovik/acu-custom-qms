ifeq ($(filter oneshell,$(.FEATURES)),)
$(error GNU Make ≥ 3.82 required (this is $(MAKE_VERSION) from $(MAKE)). On macOS: brew install make && gmake <target>)
endif

.EXPORT_ALL_VARIABLES:
.ONESHELL:
.SILENT:

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
MAKEFLAGS += --no-builtin-rules --no-builtin-variables
export PATH := $(abspath .venv)/bin:$(PATH)

UV ?= uv
QMS_DLL := src/Lab5.QMS/bin/Release/Lab5.QMS.dll
# Unbuffered unittest so a stuck e2e test prints its name. Process-level
# backstop (seconds) via faulthandler in e2e/helper.py; 0 disables.
PYTHONUNBUFFERED := 1
E2E_TIMEOUT ?= 900

default: help

.PHONY: help check test pack dll clean preflight release major minor patch

###############################################################################
# Tests
###############################################################################

# PATH `acu` from `uv tool install acumatica-cli`. Never `uv run acu`.
# Never `acu check` from this repo (destructive tenant rebuild).

test: .venv ## Local unit tests (no live tenant)
	$(call header,Running unit tests)
	$(UV) run python -u -m unittest discover -s tests -p 'test_*.py' -v

pack: dll ## Build Lab5_QMS_Customization.zip
	$(call header,Packing Lab5_QMS_Customization.zip)
	$(UV) run lab5-qms pack

dll: $(QMS_DLL) ## Compile Lab5.QMS.dll on the ERP VM (SSH) if missing

# File target: compile only when the assembly is absent. Order-only .venv
# so `uv sync` does not force a rebuild. No source prereqs — `gmake dll`
# with an existing file is a no-op.
$(QMS_DLL): | .venv
	test -e .env || { echo ".env missing — decrypt .env.gpg at the repo root"; exit 1; }
	$(call header,Building Lab5.QMS.dll via SSH)
	$(UV) run python dll.py

clean: ## Remove compiled DLL, pack zip, and temp artifacts
	$(call header,Cleaning)
	rm -rf src/Lab5.QMS/bin src/Lab5.QMS/obj
	rm -f Lab5_QMS_Customization.zip
	rm -rf .ruff_cache .pytest_cache findings .vs
	find . \( -path './.venv' -o -path './.git' \) -prune -o \
		-name '__pycache__' -type d -exec rm -rf {} +
	find . \( -path './.venv' -o -path './.git' \) -prune -o \
		\( -name '*.pyc' -o -name '.DS_Store' -o -name '*.user' \
		   -o -name '*.suo' \) -delete

preflight: .venv ## Read-only acu config check against .env
	test -e .env || { echo ".env missing — decrypt .env.gpg at the repo root"; exit 1; }
	command -v acu >/dev/null \
		|| { echo "acu not on PATH — uv tool install acumatica-cli"; exit 1; }
	$(call header,acu config check)
	acu config check

# `gmake check FILE=<path-or-stem>` scopes to one e2e file; unset = whole tier.
check_target := $(if $(FILE),$(firstword $(wildcard $(FILE) e2e/$(FILE) e2e/$(FILE).py)),e2e)

check: test preflight $(QMS_DLL) ## Live e2e vs .env tenant (acu CLI + REST; publishes Lab5.QMS)
	test -n "$(check_target)" || { echo "no e2e file matches FILE=$(FILE)"; exit 1; }
	$(call header,Live e2e)
	if [[ "$(check_target)" == *.py ]]; then
		$(UV) run python -u -m unittest discover -s e2e -p "$$(basename "$(check_target)")" -t . -v
	else
		$(UV) run python -u -m unittest discover -s e2e -t . -v
	fi

###############################################################################
# Release
###############################################################################

# `gmake release <part>` passes the part as an extra goal; pick it out and
# give the part words no-op recipes so make does not try to build them.
# There is no CI publisher — this recipe tags, packs the zip, and runs
# `gh release create` locally (unlike acumatica-cli).
part := $(word 1,$(filter major minor patch,$(MAKECMDGOALS)))

release: test $(QMS_DLL) ## Bump version, promote CHANGELOG, pack zip, tag, push, gh release
	test -n "$(part)" || { echo "usage: gmake release major|minor|patch"; exit 1; }
	git diff --quiet && git diff --cached --quiet \
		|| { echo "working tree not clean — commit or stash first"; exit 1; }
	command -v gh >/dev/null \
		|| { echo "gh CLI required — https://cli.github.com/"; exit 1; }
	gh auth status >/dev/null 2>&1 \
		|| { echo "gh not authenticated — run: gh auth login"; exit 1; }
	$(call header,Checking CHANGELOG Unreleased has shippable bullets)
	./Scripts/changelog check
	$(call header,Bumping $(part) version)
	$(UV) version --bump $(part)
	version=$$($(UV) version --short)
	$(call header,Promoting CHANGELOG Unreleased → v$$version)
	./Scripts/changelog promote "$$version"
	git add pyproject.toml uv.lock CHANGELOG.md
	git commit -m "chore: release v$$version"
	git tag "v$$version"
	$(call header,Packing Lab5_QMS_Customization.zip)
	$(UV) run lab5-qms pack
	$(call header,Pushing v$$version)
	git push && git push --tags
	$(call header,Creating GitHub release v$$version)
	./Scripts/changelog notes "$$version" | gh release create "v$$version" \
		--title "v$$version" \
		--notes-file - \
		--verify-tag \
		Lab5_QMS_Customization.zip
	echo "$(green)Released v$$version$(reset)"

major minor patch:
	@:

###############################################################################
# Python env
###############################################################################

.venv: uv.lock
	$(UV) venv --clear && hash -r && $(UV) sync

uv.lock: pyproject.toml
	$(UV) lock --upgrade && touch $(@)

###############################################################################
# Colors and Headers
###############################################################################

TERM := xterm-256color

blue := $$(tput setaf 4)
green := $$(tput setaf 2)
yellow := $$(tput setaf 3)
reset := $$(tput sgr0)

define header
echo "$(blue)==> $(1) <==$(reset)"
endef

help:
	echo "$(blue)Usage: $(green)gmake [recipe]$(reset)"
	echo "$(blue)Recipes:$(reset)"
	awk 'BEGIN {FS = ":.*?## "; sort_cmd = "sort"} /^[a-zA-Z0-9_-]+:.*?## / \
	{ printf "  \033[33m%-10s\033[0m %s\n", $$1, $$2 | sort_cmd; } \
	END {close(sort_cmd)}' $(MAKEFILE_LIST)
