.PHONY: docs

# set default shell
SHELL := $(shell which bash)

# src dirs and files
SRCDIRS = gptme tests scripts train
SRCFILES = $(shell find ${SRCDIRS} -name '*.py')

# exclude files
EXCLUDES = tests/output scripts/build_changelog.py
SRCFILES = $(shell find ${SRCDIRS} -name '*.py' $(foreach EXCLUDE,$(EXCLUDES),-not -path $(EXCLUDE)))

build:
	poetry install

build-docker:
	docker build . -t gptme:latest -f Dockerfile
	docker build . -t gptme-eval:latest -f Dockerfile.eval

test:
	@# if SLOW is not set, pass `-m "not slow"` to skip slow tests
	poetry run pytest ${SRCDIRS} -v --log-level INFO --durations=5 \
		--cov=gptme --cov-report=xml --cov-report=term-missing --cov-report=html --junitxml=junit.xml \
		-n 8 \
		$(if $(EVAL), , -m "not eval") \
		$(if $(SLOW), --timeout 60 --retries 2 --retry-delay 5, --timeout 5 -m "not slow and not eval") \
		$(if $(PROFILE), --profile-svg)

eval:
	poetry run gptme-eval

typecheck:
	poetry run mypy --ignore-missing-imports --check-untyped-defs ${SRCDIRS} $(if $(EXCLUDES),$(foreach EXCLUDE,$(EXCLUDES),--exclude $(EXCLUDE)))

lint:
	poetry run ruff check ${SRCDIRS}

format:
	poetry run ruff check --fix-only ${SRCDIRS}
	poetry run pyupgrade --py310-plus --exit-zero-even-if-changed ${SRCFILES}
	poetry run black ${SRCDIRS}

precommit: format lint typecheck test

docs/.clean: docs/conf.py
	poetry run make -C docs clean
	touch docs/.clean

docs: docs/conf.py docs/*.rst docs/.clean
	poetry run make -C docs html

.PHONY: site
site: site/dist/index.html site/dist/docs

site/dist/index.html: README.md
	mkdir -p site/dist
	pandoc -s -f gfm -t html5 -o $@ $< --metadata title=" "
	cp -r media site/dist

site/dist/docs: docs
	cp -r docs/_build/html site/dist/docs

version:
	@./scripts/bump_version.sh

./scripts/build_changelog.py:
	wget -O $@ https://raw.githubusercontent.com/ActivityWatch/activitywatch/master/scripts/build_changelog.py
	chmod +x $@

dist/CHANGELOG.md: version ./scripts/build_changelog.py
	VERSION=$$(git describe --tags --abbrev=0) && \
	PREV_VERSION=$$(./scripts/get-last-version.sh $${VERSION}) && \
		./scripts/build_changelog.py --range $${PREV_VERSION}...$${VERSION} --project-title gptme --org ErikBjare --repo gptme --output $@

release: dist/CHANGELOG.md
	@VERSION=$$(git describe --tags --abbrev=0) && \
		echo "Releasing version $${VERSION}"; \
		read -p "Press enter to continue" && \
		gh release create $${VERSION} -t $${VERSION} -F dist/CHANGELOG.md

clean: clean-docs clean-site clean-test

clean-site:
	rm -rf site/dist

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

bench-importtime:
	time poetry run python -X importtime -m gptme --model openrouter --non-interactive 2>&1 | grep "import time" | cut -d'|' -f 2- | sort -n
