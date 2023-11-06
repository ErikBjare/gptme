.PHONY: docs

SRCDIRS = gptme tests scripts train
SRCFILES = $(shell find ${SRCDIRS} -name '*.py')
EXCLUDES = tests/output

# Check if playwright is installed (for browser tests)
HAS_PLAYWRIGHT := $(shell poetry run command -v playwright 2> /dev/null)

build:
	poetry install

test:
	@# if SLOW is not set, pass `-m "not slow"` to skip slow tests
	poetry run pytest ${SRCDIRS} -v --log-level INFO --durations=5 \
		--cov=gptme --cov-report=xml --cov-report=term-missing --cov-report=html \
		$(if $(SLOW),, -m "not slow") \
		$(if $(PROFILE), --profile-svg) \
		$(if $(HAS_PLAYWRIGHT), --cov-config=scripts/.coveragerc-playwright)

typecheck:
	poetry run mypy --ignore-missing-imports ${SRCDIRS} --exclude ${EXCLUDES}

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
