build:
	poetry install

test:
	@# if SLOW is not set, pass `-m "not slow"` to skip slow tests
	poetry run pytest tests -v --cov=gptme --cov-report=term-missing --cov-report=html $(if $(SLOW),, -m "not slow") $(if $(PROFILE),--profile-svg)

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
