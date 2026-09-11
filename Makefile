ifeq ($(filter notintermediate,$(.FEATURES)),)
$(error GNU Make ≥ 4.4 required (this is $(MAKE_VERSION) from $(MAKE)). On macOS: brew install make && gmake <target>)
endif

.SILENT:

SHELL := /bin/sh
MAKEFLAGS += --no-builtin-rules --no-builtin-variables
export PATH := $(abspath .venv)/bin:$(PATH)

UV ?= uv
# Unbuffered unittest so a stuck e2e test prints its name. Process-level
# backstop (seconds) via faulthandler in e2e/helper.py; 0 disables.
export PYTHONUNBUFFERED := 1
export E2E_TIMEOUT ?= 900

empty :=
space := $(empty) $(empty)
s := $(shell printf '\036')
esc := $(shell printf '\033')
blue := $(esc)[34m
green := $(esc)[32m
yellow := $(esc)[33m
reset := $(esc)[0m

header = $(info $(blue)==> $1 <==$(reset))

# Short flags live in the first MAKEFLAGS word (`nprR`). `-n` is `n` there;
# later words (`--jobserver-auth=...`) also contain `n` and must be ignored.
dry-run = $(findstring n,$(firstword $(MAKEFLAGS)))

need-env = $(if $(dry-run),,$(if $(wildcard .env),,$(error .env missing — decrypt .env.gpg at the repo root)))
need-acu = $(if $(dry-run),,$(if $(shell command -v acu),,$(error acu not on PATH — uv tool install acumatica-cli)))
need-gh = $(if $(dry-run),,$(if $(shell command -v gh),,$(error gh CLI required — https://cli.github.com/)))
need-gh-auth = $(if $(dry-run),,$(shell gh auth status >/dev/null 2>&1)$(if $(filter 0,$(.SHELLSTATUS)),,$(error gh not authenticated — run: gh auth login)))
need-clean = $(if $(dry-run),,$(if $(shell git status --porcelain),$(error working tree not clean — commit or stash first)))
need-part = $(if $(part),,$(error usage: gmake release major|minor|patch))

# Recursive glob. `*` skips dot-dirs (.git, .venv).
rwildcard = $(strip \
	$(wildcard $(1)$(2)) \
	$(foreach d,$(wildcard $(1)*),$(if $(wildcard $(d)/.),$(call rwildcard,$(d)/,$(2)))))

default: help

.PHONY: help check e2e build deploy clean preflight release major minor patch
.PHONY: _release-pre _release-bump _release-tag _release-pack _release-gh

###############################################################################
# Tests
###############################################################################

# PATH `acu` from `uv tool install acumatica-cli`. Never `uv run acu`.
# Never `acu check` from this repo (destructive tenant rebuild).

check: .venv ## Format check, lint, local unit tests (no live tenant)
	$(call header,Running unit tests)
	$(UV) run ruff format --check
	$(UV) run ruff check
	$(UV) run python -u -m unittest discover -s tests -p 'test_*.py' -v

build: .venv ## Build Lab5_QMS_Customization.zip
	$(call header,Building Lab5_QMS_Customization.zip)
	$(UV) run lab5-qms pack

deploy: .venv ## Pack, publish Lab5.QMS, seed Role + QM rights
	$(call need-env)
	$(call need-acu)
	$(call header,Deploying Lab5.QMS)
	$(UV) run lab5-qms deploy

clean: ## Remove compiled DLL, pack zip, and temp artifacts
	$(call header,Cleaning)
	rm -rf QMS/Lab5.QMS/bin QMS/Lab5.QMS/obj .ruff_cache .pytest_cache findings .vs $(call rwildcard,,__pycache__)
	rm -f Lab5_QMS_Customization.zip .release-notes $(call rwildcard,,*.pyc) $(call rwildcard,,.DS_Store) $(call rwildcard,,*.user) $(call rwildcard,,*.suo)

preflight: .venv ## Read-only acu config check against .env
	$(call need-env)
	$(call need-acu)
	$(call header,acu config check)
	acu config check

# `gmake e2e FILE=<path-or-stem>` scopes to one e2e file; unset = whole tier.
e2e_target := $(if $(FILE),$(firstword $(wildcard $(FILE) e2e/$(FILE) e2e/$(FILE).py)),e2e)
ifneq ($(filter e2e,$(MAKECMDGOALS)),)
$(if $(FILE),$(if $(e2e_target),,$(error no e2e file matches FILE=$(FILE))))
endif

e2e: check preflight ## Live e2e vs .env tenant (acu CLI + REST; publishes Lab5.QMS)
	$(call header,Live e2e)
	$(UV) run python dll.py
	$(if $(filter %.py,$(e2e_target)),\
		$(UV) run python -u -m unittest discover -s e2e -p '$(notdir $(e2e_target))' -t . -v,\
		$(UV) run python -u -m unittest discover -s e2e -t . -v)

###############################################################################
# Release
###############################################################################

# `gmake release <part>` passes the part as an extra goal; pick it out and
# give the part words no-op recipes so make does not try to build them.
# There is no CI publisher — this recipe tags, packs the zip, and runs
# `gh release create` locally (unlike acumatica-cli).
# Chain splits around `uv version --bump` so $(VERSION) is read after the bump.
part := $(firstword $(filter major minor patch,$(MAKECMDGOALS)))
ifneq ($(filter release,$(MAKECMDGOALS)),)
$(if $(part),,$(error usage: gmake release major|minor|patch))
endif
VERSION = $(shell $(UV) version --short)

release: check _release-gh ## Bump version, promote CHANGELOG, pack zip, tag, push, gh release

_release-pre: check
	$(call need-part)
	$(call need-clean)
	$(call need-gh)
	$(call need-gh-auth)
	$(call header,Checking CHANGELOG Unreleased has shippable bullets)
	./changelog check
	$(call need-env)
	$(UV) run python dll.py

_release-bump: _release-pre
	$(call header,Bumping $(part) version)
	$(UV) version --bump $(part)

_release-tag: _release-bump
	$(call header,Promoting CHANGELOG Unreleased → v$(VERSION))
	./changelog promote "$(VERSION)"
	git add pyproject.toml uv.lock CHANGELOG.md
	git commit -m "chore: release v$(VERSION)"
	git tag "v$(VERSION)"

_release-pack: _release-tag
	$(call header,Packing Lab5_QMS_Customization.zip)
	$(UV) run lab5-qms pack

_release-gh: _release-pack
	$(call header,Pushing v$(VERSION))
	git push
	git push --tags
	$(call header,Creating GitHub release v$(VERSION))
	./changelog notes "$(VERSION)" > .release-notes
	gh release create "v$(VERSION)" \
		--title "v$(VERSION)" \
		--notes-file .release-notes \
		--verify-tag \
		Lab5_QMS_Customization.zip
	rm -f .release-notes
	$(info $(green)Released v$(VERSION)$(reset))

major minor patch: ;

###############################################################################
# Python env
###############################################################################

.venv: uv.lock
	$(UV) venv --clear
	$(UV) sync

uv.lock: pyproject.toml
	$(UV) lock --upgrade
	touch $@

###############################################################################
# Help
###############################################################################

# Target-line double-hash descriptions, read with $(file) and split with $(let).
help-src := $(file < $(firstword $(MAKEFILE_LIST)))
help-words := $(foreach w,$(subst $(space),$(s),$(help-src)),$(if $(and $(findstring $(s)##$(s),$(w)),$(filter-out \#%,$(w))),$(w)))
pad-check := check$(space)$(space)$(space)$(space)$(space)
pad-clean := clean$(space)$(space)$(space)$(space)$(space)
pad-deploy := deploy$(space)$(space)$(space)$(space)
pad-build := build$(space)$(space)$(space)$(space)$(space)
pad-preflight := preflight$(space)
pad-release := release$(space)$(space)$(space)
pad-e2e := e2e$(space)$(space)$(space)$(space)$(space)$(space)$(space)
pad10 = $(or $(pad-$1),$1)
show-help = $(let tgt desc,$(subst $(s)##$(s), ,$1),$(let name text,$(patsubst %:,%,$(firstword $(subst $(s),$(space),$(tgt)))) $(strip $(subst $(s),$(space),$(desc))),$(info   $(yellow)$(call pad10,$(name))$(reset) $(text))))

help:
	$(info $(blue)Usage: $(green)gmake [recipe]$(reset))
	$(info $(blue)Recipes:$(reset))
	$(foreach w,$(sort $(help-words)),$(call show-help,$(w)))
	:
