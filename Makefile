.DEFAULT_GOAL := all
isort = isort watchfiles tests
black = black watchfiles tests

.PHONY: install
install:
	pip install -U pip pre-commit
	pip install -r requirements/all.txt
	pip install -e .
	pre-commit install

.PHONY: build-dev
build-dev:
	pip uninstall -y watchfiles
	@rm -f watchfiles/*.so
	cargo build
	@rm -f target/debug/lib_rust_notify.d
	@mv target/debug/lib_rust_notify.* watchfiles/_rust_notify.so

.PHONY: format
format:
	$(isort)
	$(black)
	@echo 'max_width = 120' > .rustfmt.toml
	cargo fmt

.PHONY: lint-python
lint-python:
	flake8 --max-complexity 10 --max-line-length 120 --ignore E203,W503 watchfiles tests
	$(isort) --check-only --df
	$(black) --check --diff

.PHONY: lint-rust
lint-rust:
	cargo fmt --version
	@echo 'max_width = 120' > .rustfmt.toml
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
