.DEFAULT_GOAL := all

.PHONY: .uv
.uv: ## Check that uv is installed
	@uv --version || echo 'Please install uv: https://docs.astral.sh/uv/getting-started/installation/'

.PHONY: .pre-commit
.pre-commit: ## Check that pre-commit is installed
	@pre-commit -V || echo 'Please install pre-commit: https://pre-commit.com/'

.PHONY: install
install: .uv .pre-commit ## Install the package, dependencies, and pre-commit for local development
	uv sync --frozen --group lint --group docs
	pre-commit install --install-hooks

.PHONY: build-dev
build-dev:
	uv run maturin develop --uv

.PHONY: format
format:
	uv run ruff check --fix-only watchfiles tests
	uv run ruff format watchfiles tests
	cargo fmt

.PHONY: lint-python
lint-python:
	uv run ruff check watchfiles tests
	uv run ruff format --check watchfiles tests

.PHONY: lint-rust
lint-rust:
	cargo fmt --version
	cargo fmt --all -- --check
	cargo clippy --version
	cargo clippy -- -D warnings

.PHONY: lint
lint: lint-python lint-rust

.PHONY: mypy
mypy:
	uv run mypy watchfiles

.PHONY: test
test:
	uv run coverage run -m pytest

.PHONY: testcov
testcov: test
	@echo "building coverage html"
	@uv run coverage html

.PHONY: docs
docs:
	rm -f watchfiles/*.so
	uv run --no-sync mkdocs build

.PHONY: all
all: lint mypy testcov docs

.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*.so' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -f tests/__init__.py
	rm -rf .cache
	rm -rf htmlcov
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -rf build
