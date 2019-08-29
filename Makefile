.DEFAULT_GOAL := all
isort = isort -rc watchgod tests

.PHONY: install
install:
	pip install -U setuptools pip
	pip install -r tests/requirements.txt
	pip install -U .

.PHONY: isort
format:
	$(isort)

.PHONY: lint
lint:
	python setup.py check -rms
	flake8 watchgod/ tests/
	$(isort) --check-only

.PHONY: test
test:
	pytest --cov=watchgod --log-format="%(levelname)s %(message)s"

.PHONY: testcov
testcov: test
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
