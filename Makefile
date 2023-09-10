build:
	poetry install

test:
	@# pass `-m "not slow"` to skip slow tests if SLOW is not set
	poetry run pytest tests -v --cov=gptme --cov-report=term-missing --cov-report=html $(if $(SLOW),, -m "not slow")

typecheck:
	poetry run mypy --ignore-missing-imports gptme

lint:
	poetry run ruff gptme/* tests/*

format:
	poetry run black gptme tests

precommit:
	make test
	make typecheck
	make lint
