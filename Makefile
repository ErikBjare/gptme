.PHONY: docs eval

# set default shell
SHELL := $(shell which bash)

# src dirs and files
SRCDIRS = gptme tests scripts train eval
SRCFILES = $(shell find ${SRCDIRS} -name '*.py')

# exclude files
EXCLUDES = tests/output scripts/build_changelog.py
SRCFILES = $(shell find ${SRCDIRS} -name '*.py' $(foreach EXCLUDE,$(EXCLUDES),-not -path $(EXCLUDE)))

# Check if playwright is installed (for browser tests)
HAS_PLAYWRIGHT := $(shell poetry run command -v playwright 2> /dev/null)

build:
	poetry install

test:
	@# if SLOW is not set, pass `-m "not slow"` to skip slow tests
	poetry run pytest ${SRCDIRS} -v --log-level INFO --durations=5 \
		--cov=gptme --cov-report=xml --cov-report=term-missing --cov-report=html \
		-n auto \
		$(if $(SLOW),, -m "not slow") \
		$(if $(PROFILE), --profile-svg) \
		$(if $(HAS_PLAYWRIGHT), --cov-config=scripts/.coveragerc-playwright)

eval:
	cd eval && poetry run python main.py

typecheck:
	poetry run mypy --ignore-missing-imports ${SRCDIRS} $(if $(EXCLUDES),$(foreach EXCLUDE,$(EXCLUDES),--exclude $(EXCLUDE)))

lint:
	poetry run ruff ${SRCDIRS}

format:
	poetry run ruff --fix-only ${SRCDIRS}
	poetry run pyupgrade --py310-plus --exit-zero-even-if-changed ${SRCFILES}
	poetry run black ${SRCDIRS}

precommit: format lint typecheck test

docs:
	poetry run make -C docs html

clean-test:
	echo $$HOME/.local/share/gptme/logs/*test-*-test_*
	rm -I $$HOME/.local/share/gptme/logs/*test-*-test_*/*.jsonl || true
	rm --dir $$HOME/.local/share/gptme/logs/*test-*-test_*/ || true
