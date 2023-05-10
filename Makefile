build:
	poetry install

test:
	poetry run pytest tests -v --cov=gpt_playground --cov=gptme --cov-report=term-missing --cov-report=html

typecheck:
	poetry run mypy --ignore-missing-imports gpt_playground gptme

lint:
	poetry run ruff gpt_playground/* gptme/*

precommit:
	make test
	make typecheck
	make lint
