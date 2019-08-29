.DEFAULT_GOAL := all

.PHONY: install
install:
	pip install -U setuptools pip
	pip install -r tests/requirements.txt
	pip install -U .

.PHONY: isort
isort:
	isort -rc -w 120 watchgod
	isort -rc -w 120 tests

.PHONY: lint
lint:
	python setup.py check -rms
	flake8 watchgod/ tests/
	isort -rc --check-only watchgod tests

.PHONY: test
test:
	pytest --cov=watchgod

.PHONY: testcov
testcov:
	pytest --cov=watchgod
	@echo "building coverage html"
	@coverage html

.PHONY: all
all: testcov lint

.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -rf .cache
	rm -rf htmlcov
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -rf build
	python setup.py clean
