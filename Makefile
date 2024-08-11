.PHONY: docs eval

# set default shell
SHELL := $(shell which bash)

# src dirs and files
SRCDIRS = gptme tests scripts train eval
SRCFILES = $(shell find ${SRCDIRS} -name '*.py')

# exclude files
EXCLUDES = tests/output scripts/build_changelog.py
SRCFILES = $(shell find ${SRCDIRS} -name '*.py' $(foreach EXCLUDE,$(EXCLUDES),-not -path $(EXCLUDE)))

build:
	poetry install

test:
	@# if SLOW is not set, pass `-m "not slow"` to skip slow tests
	poetry run pytest ${SRCDIRS} -v --log-level INFO --durations=5 \
		--cov=gptme --cov-report=xml --cov-report=term-missing --cov-report=html \
		-n 8 \
		$(if $(SLOW), --timeout 60, --timeout 5 -m "not slow") \
		$(if $(EVAL), , -m "not eval") \
		$(if $(PROFILE), --profile-svg)

eval:
	poetry run python3 -m eval

typecheck:
	poetry run mypy --ignore-missing-imports ${SRCDIRS} $(if $(EXCLUDES),$(foreach EXCLUDE,$(EXCLUDES),--exclude $(EXCLUDE)))

lint:
	poetry run ruff ${SRCDIRS}

format:
	poetry run ruff --fix-only ${SRCDIRS}
	poetry run pyupgrade --py310-plus --exit-zero-even-if-changed ${SRCFILES}
	poetry run black ${SRCDIRS}

precommit: format lint typecheck test

docs/.clean: docs/conf.py
	poetry run make -C docs clean
	touch docs/.clean

docs: docs/conf.py docs/*.rst docs/.clean
	poetry run make -C docs html

# Makes sure that the pyproject.toml is set to the latest tagged version, and if not, bumps the version to the latest tag in a new commit
version:
	@git diff --cached --exit-code || (echo "There are staged files, please commit or unstage them" && exit 1)
	@git diff --exit-code pyproject.toml || (echo "pyproject.toml is dirty, please commit or stash changes" && exit 1)
	git pull
	@VERSION=$$(git describe --tags --abbrev=0 | cut -b 2-) && \
		poetry version $${VERSION} && \
		git add pyproject.toml && \
		git commit -m "chore: bump version to $${VERSION}" || echo "No version bump needed"

./scripts/build_changelog.py:
	wget -O $@ https://raw.githubusercontent.com/ActivityWatch/activitywatch/master/scripts/build_changelog.py

dist/CHANGELOG.md: version ./scripts/build_changelog.py
	VERSION=$$(git describe --tags --abbrev=0) && \
		./scripts/build_changelog.py --range $$(./scripts/get-last-version.sh $${VERSION})...$${VERSION} --project-title gptme --org ErikBjare --repo gptme --output $@

release: dist/CHANGELOG.md
	@VERSION=$$(git describe --tags --abbrev=0) && \
		echo "Releasing version $${VERSION}"; \
		read -p "Press enter to continue" && \
		gh release create $${VERSION} -t $${VERSION} -F dist/CHANGELOG.md

clean: clean-docs

clean-docs:
	poetry run make -C docs clean

clean-test:
	echo $$HOME/.local/share/gptme/logs/*test-*-test_*
	rm -I $$HOME/.local/share/gptme/logs/*test-*-test_*/*.jsonl || true
	rm --dir $$HOME/.local/share/gptme/logs/*test-*-test_*/ || true

cloc: cloc-core cloc-tools cloc-server cloc-tests

cloc-core:
	cloc gptme/*.py gptme/*/__init__.py gptme/*/base.py --by-file

cloc-tools:
	cloc gptme/tools/*.py --by-file

cloc-server:
	cloc gptme/server --by-file

cloc-tests:
	cloc tests/*.py --by-file
