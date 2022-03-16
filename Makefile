.DEFAULT_GOAL := all
isort = isort watchgod tests setup.py
black = black watchgod tests setup.py

.PHONY: install
install:
	pip install -U pip
	pip install -r tests/requirements.txt
	pip install -U .

.PHONY: install-all
install-all: install
	pip install -r tests/requirements-linting.txt

.PHONY: build-dev
build-dev:
	python setup.py develop

.PHONY: build-prod
build-prod:
	python setup.py install

.PHONY: isort
format:
	$(isort)
	$(black)
	cargo fmt

.PHONY: lint
lint:
	python setup.py check -ms
	flake8 --max-complexity 10 --max-line-length 120 --ignore E203,W503 watchgod tests setup.py
	$(isort) --check-only --df
	$(black) --check --diff
	cargo fmt --version
	cargo fmt --all -- --check
	cargo clippy --version
	cargo clippy -- -D warnings

.PHONY: mypy
mypy:
	mypy watchgod

.PHONY: test
test:
	pytest --cov=watchgod --log-format="%(levelname)s %(message)s"

.PHONY: testcov
testcov: test
	@echo "building coverage html"
	@coverage html

.PHONY: all
all: lint mypy testcov

.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -rf .cache
	rm -rf htmlcov
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -rf build
	python setup.py clean
