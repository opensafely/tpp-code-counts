# Notes for developers

## System requirements

### just

Follow installation instructions from the [Just Programmer's Manual](https://just.systems/man/en/chapter_4.html) for your OS.

Add completion for your shell. E.g. for bash:

```bash
source <(just --completions bash)
```

Show all available commands:

```bash
just
```

### uv

Follow installation instructions from the [uv documentation](https://docs.astral.sh/uv/getting-started/installation/) for your OS.

## Local development environment

Set up a local development environment with:

```bash
just devenv
```

## Testing

### Overview

This project includes tests that run real T-SQL queries against a fully functioning MSSQL instance running in Docker. This is so that the queries can be tested against the exact SQL compatibility setting currently available on the TPP back end.

### Prerequisites for SQL tests

To run SQL tests locally you must have:

- **Docker installed and running**
- **The sqlrunner repo checked out at `../sqlrunner`** (i.e., as a sibling directory to this repository)

The SQL test helper will raise an error if sqlrunner is not found in that location.

### How SQL tests work

SQL tests use the helpers in `tests/mssql_test_helper.py`, which:

1. Starts (or reuses) an MSSQL Docker container named `sqlrunner-mssql`
2. Loads database setup scripts from the sqlrunner repo
3. Creates the necessary tables (e.g., `APCS`, `APCS_Der`, `ONS_Deaths`)
4. Populates them with test data from the test files
5. Executes the relevant SQL queries from `analysis/query_icd10_apcs.sql` and `analysis/query_icd10_ons_deaths.sql`

### Running tests

Run all tests:

```bash
just test
```
