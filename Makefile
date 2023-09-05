build:
	poetry install

test:
	poetry run pytest tests -v --cov=gptme --cov-report=term-missing --cov-report=html

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
