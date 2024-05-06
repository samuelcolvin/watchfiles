.DEFAULT_GOAL := all

.PHONY: install
install:
	pip install -U pip pre-commit maturin
	pip install -r requirements/all.txt
	pip install -e .
	pre-commit install

.PHONY: update-lockfiles
update-lockfiles:
	@echo "Updating requirements files using pip-compile"
	pip-compile -q --strip-extras -o requirements/linting.txt requirements/linting.in
	pip-compile -q --strip-extras -c requirements/linting.txt -o requirements/pyproject.txt pyproject.toml
	pip-compile -q --strip-extras -c requirements/linting.txt -c requirements/pyproject.txt -o requirements/testing.txt requirements/testing.in
	pip-compile -q --strip-extras -c requirements/linting.txt -c requirements/pyproject.txt -c requirements/testing.txt -o requirements/docs.txt requirements/docs.in
	pip install --dry-run -r requirements/all.txt

.PHONY: build-dev
build-dev:
	maturin develop

.PHONY: format
format:
	ruff check --fix-only watchfiles tests
	ruff format watchfiles tests
	@echo 'max_width = 120' > .rustfmt.toml
	cargo fmt

.PHONY: lint-python
lint-python:
	ruff check watchfiles tests
	ruff format --check watchfiles tests

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
	mypy watchfiles

.PHONY: test
test:
	coverage run -m pytest

.PHONY: testcov
testcov: test
	@echo "building coverage html"
	@coverage html

.PHONY: docs
docs:
	rm -f watchfiles/*.so
	mkdocs build

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
