set dotenv-load := true
set positional-arguments := true

# List available commands
default:
    @"{{ just_executable() }}" --list

# Clean up temporary files
clean:
    rm -rf .venv
    rm -rf .pytest_cache
    rm -rf .coverage
    rm -rf htmlcov
    rm -rf analysis/__pycache__
    rm -rf analysis/.pytest_cache

# Install dev requirements into venv
devenv:
    uv sync

# *args is variadic, 0 or more. This allows us to do `just test -k match`, for example.

# Run the tests
test *args:
    uv run coverage run --module pytest "$@"
    uv run coverage report || uv run coverage html

# Run tests without coverage
test-quick *args:
    uv run pytest "$@"

# Check formatting (does not change any files)
format *args:
    uv run ruff format --diff --quiet "$@"

# Check for linting errors
lint *args:
    uv run ruff check "$@"

# Run all dev checks (does not change any files)
check:
    #!/usr/bin/env bash
    set -euo pipefail

    failed=0

    check() {
        echo -e "\e[1m=> ${1}\e[0m"
        rc=0
        eval $1 || rc=$?
        if [[ $rc != 0 ]]; then
            failed=$((failed + 1))
            echo -e "\n"
        fi
    }

    check "just format ."
    check "just lint ."

    if [[ $failed > 0 ]]; then
        echo -en "\e[1;31m"
        echo "   $failed checks failed"
        echo -e "\e[0m"
        exit 1
    fi

# Fix formatting and linting issues
fix:
    -uv run ruff check --fix .
    -uv run ruff format .
    -just --fmt --unstable

# Upgrade a single package to the latest version as of the cutoff in pyproject.toml
upgrade-package package: && devenv
    uv lock --upgrade-package {{ package }}

# Upgrade all packages to the latest versions as of the cutoff in pyproject.toml
upgrade-all: && devenv
    uv lock --upgrade
