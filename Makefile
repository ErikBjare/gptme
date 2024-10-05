.PHONY: docs

# set default shell
SHELL := $(shell which bash)

# src dirs and files
SRCDIRS = gptme tests scripts
SRCFILES = $(shell find ${SRCDIRS} -name '*.py')

# exclude files
EXCLUDES = tests/output scripts/build_changelog.py
SRCFILES = $(shell find ${SRCDIRS} -name '*.py' $(foreach EXCLUDE,$(EXCLUDES),-not -path $(EXCLUDE)))

build:
	poetry install

build-docker:
	docker build . -t gptme:latest -f scripts/Dockerfile
	docker build . -t gptme-eval:latest -f scripts/Dockerfile.eval

build-docker-full:
	docker build . -t gptme-eval:latest -f scripts/Dockerfile.eval --build-arg RUST=yes --build-arg BROWSER=yes

test:
	@# if SLOW is not set, pass `-m "not slow"` to skip slow tests
	poetry run pytest ${SRCDIRS} -v --log-level INFO --durations=5 \
		--cov=gptme --cov-report=xml --cov-report=term-missing --cov-report=html --junitxml=junit.xml \
		-n 16 \
		$(if $(EVAL), , -m "not eval") \
		$(if $(SLOW), --timeout 60 --retries 2 --retry-delay 5, --timeout 10 -m "not slow and not eval") \
		$(if $(PROFILE), --profile-svg)

eval:
	poetry run gptme-eval

typecheck:
	poetry run mypy --ignore-missing-imports --check-untyped-defs ${SRCDIRS} $(if $(EXCLUDES),$(foreach EXCLUDE,$(EXCLUDES),--exclude $(EXCLUDE)))

RUFF_ARGS=${SRCDIRS} $(foreach EXCLUDE,$(EXCLUDES),--exclude $(EXCLUDE))

lint:
	@# check there is no `ToolUse("python"` in the code (should be `ToolUse("ipython"`)
	! grep -r 'ToolUse("python"' ${SRCDIRS}
	@# ruff
	poetry run ruff check ${RUFF_ARGS}


format:
	poetry run ruff check --fix-only ${RUFF_ARGS}
	poetry run ruff format ${RUFF_ARGS}

update-models:
	wayback_url=$$(curl "https://archive.org/wayback/available?url=openai.com/api/pricing/" | jq -r '.archived_snapshots.closest.url') && \
		gptme 'update the model metadata from this page' gptme/models.py gptme/llm_openai_models.py "$${wayback_url}" --non-interactive

precommit: format lint typecheck

docs/.clean: docs/conf.py
	poetry run make -C docs clean
	touch docs/.clean

docs: docs/conf.py docs/*.rst docs/.clean
	if [ ! -e eval_results ]; then \
		if [ -e eval-results/eval_results ]; then \
			ln -s eval-results/eval_results .; \
		else \
			git fetch origin eval-results; \
			git checkout origin/eval-results -- eval_results; \
		fi \
	fi
	poetry run make -C docs html SPHINXOPTS="-W --keep-going"

.PHONY: site
site: site/dist/index.html site/dist/docs
	echo "gptme.org" > site/dist/CNAME

.PHONY: site/dist/index.html
site/dist/index.html: README.md site/dist/style.css site/template.html
	mkdir -p site/dist
	sed '1s/Website/GitHub/;1s|https://gptme.org/|https://github.com/ErikBjare/gptme|' README.md | \
	cat README.md \
		| sed '0,/Website/{s/Website/GitHub/}' - \
		| sed '0,/gptme.org\/\"/{s/gptme.org\/\"/github.com\/ErikBjare\/gptme\"/}' - \
		| pandoc -s -f gfm -t html5 -o $@ --metadata title="gptme - agent in your terminal" --css style.css --template=site/template.html
	cp -r media site/dist

site/dist/style.css: site/style.css
	mkdir -p site/dist
	cp site/style.css site/dist

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
		git push origin master $${VERSION} && \
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
	cloc gptme/*.py gptme/tools/__init__.py gptme/tools/base.py --by-file

cloc-tools:
	cloc gptme/tools/*.py --by-file

cloc-server:
	cloc gptme/server --by-file

cloc-tests:
	cloc tests/*.py --by-file

cloc-eval:
	cloc gptme/eval/**.py --by-file

cloc-total:
	cloc ${SRCFILES} --by-file

bench-importtime:
	time poetry run python -X importtime -m gptme --model openrouter --non-interactive 2>&1 | grep "import time" | cut -d'|' -f 2- | sort -n
