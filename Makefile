build:
	poetry install

test:
	poetry run pytest tests -v --cov=gpt_playground --cov-report=term-missing --cov-report=html

typecheck:
	poetry run mypy --ignore-missing-imports gpt_playground

lint:
	poetry run ruff gpt_playground/*

precommit:
	make test
	make typecheck
	make lint
