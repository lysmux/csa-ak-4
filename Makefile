UV 	       = uv run
TEST       = pytest $(arg)

.PHONY install:
install:
	uv sync --frozen
	$(UV) pre-commit install --install-hooks

############ CODE QUALITY ############
.PHONY: format ## Auto-format python source files
format:
	$(UV) ruff check --fix
	$(UV) ruff format

.PHONY: lint ## Lint python source files
lint:
	$(UV) ruff check
	$(UV) ruff format --check

.PHONY: typecheck
typecheck:
	$(UV) mypy .
############ CODE QUALITY ############

############ TESTS ############
.PHONY: test
test:
	$(UV) $(TEST) tests/

.PHONY: report
report:
	$(UV) $(TEST) tests/ --cov=./ --cov-report html
############ TESTS ############
