# Reporting Scripts

Once we have the output files from the main analysis job, we can produce various post-hoc reports and CSV files.

## Prerequisites

### Required Data Files

The scripts expect certain data files to be present in `reporting/data/`:

- **`ocl_icd10_codes.txt`**

The list of codes used in OpenCodelists can be generated from a copy of the coding database:

```bash
sqlite3 icd10_2019-covid-expanded_20190101.sqlite3 \
  "SELECT code FROM icd10_concept WHERE kind!='chapter';" | \
   sort | \
   uniq > reporting/data/ocl_icd10_codes.txt
```

- **`ehrql_codelists.json`** - Codelist usage signatures
- **`rsi-codelists-analysis.json`** - Codelist metadata (coding system, creation method)

Both of the above generated from the [OpenSAFELY variable survey repo](https://github.com/bennettoxford/opensafely-variable-survey)

- **`code_usage.zip`** - Downloaded from the job output [here](https://jobs.opensafely.org/opensafely-internal/tpp-code-counts/outputs/latest/download/)

## Scripts Overview

### 1. `missing_codes.py` - Core Usage Analysis

**Purpose**: Compares ICD-10 codes used in practice (from TPP backend) against codes available in OpenCodelists.

**Inputs**:

- `reporting/data/ocl_icd10_codes.txt`
- Remote: `jobs.opensafely.org/.../download/` (production usage data)
- Fallback: `reporting/data/code_usage.zip` (local backup)
- Fallback: `output/icd10_*.csv` (local test data)

**Outputs**:

- `reporting/outputs/code_usage_combined_apcs.csv` - All APCS codes with usage counts and `in_opencodelists` flag
- `reporting/outputs/code_usage_combined_ons_deaths.csv` - All ONS deaths codes with usage counts and `in_opencodelists` flag
- `reporting/outputs/ocl_codes_not_in_apcs.csv` - OCL codes never used in APCS data
- `reporting/outputs/ocl_codes_not_in_ons_deaths.csv` - OCL codes never used in ONS deaths data

**Run**:

```bash
python3 -m reporting.missing_codes
```

**Key Features**:

- Identifies codes missing from OpenCodelists that are used in practice
- Identifies OCL codes that never appear in actual data
- Handles 3-character codes with X-suffix padding for APCS data
- Provides warnings when remote data is unavailable (falls back to local)

---

### 2. `analyze_codelist_coverage.py` - Codelist Analysis

**Purpose**: Analyzes each ICD-10 codelist used in OpenSAFELY studies to determine completeness of descendant coverage.

**Inputs**:

- `reporting/data/ocl_icd10_codes.txt`
- `reporting/data/ehrql_codelists.json`
- `reporting/data/rsi-codelists-analysis.json`
- `reporting/outputs/code_usage_combined_apcs.csv`
- `reporting/outputs/code_usage_combined_ons_deaths.csv`

**Outputs**:

- `reporting/outputs/codelist_coverage_detail_apcs.csv`
- `reporting/outputs/codelist_coverage_detail_ons_deaths.csv`

**Run**:

```bash
python3 -m reporting.analyze_codelist_coverage
```

**Key Features**:

- Downloads codelists from OpenCodelists API (cached in `reporting/data/codelist_cache/`)
- Classifies each code as COMPLETE, PARTIAL, or NONE based on descendant coverage
- Identifies missing descendant codes that could increase coverage
- Handles both named codelists and inline code lists from ehrQL
- Separate analysis for APCS vs ONS deaths data sources

**Code Classifications**:

- **COMPLETE**: All descendants are in the codelist (or code has no descendants/is 4-char)
- **PARTIAL**: Some but not all descendants are in the codelist
- **NONE**: No descendants from OCL are in the codelist
- **EXTRA**: Descendant codes found in usage data but not in OCL

---

### 3. `analyze_prefix_matching.py` - Prefix Matching Impact Analysis

**Purpose**: Analyzes how different prefix matching assumptions affect event counts for codelists, and maps affected codelists to GitHub repositories.

**Inputs**:

- `reporting/outputs/codelist_coverage_detail_apcs.csv`
- `reporting/data/ehrql_codelists.json`

**Outputs**:

- `reporting/outputs/prefix_matching_analysis.csv` - Per-codelist event counts under different scenarios
- `reporting/outputs/prefix_matching_analysis.md` - Markdown report
- `reporting/outputs/prefix_matching_repos.csv` - Codelists with discrepancies mapped to repos

**Run**:

```bash
python3 reporting/analyze_prefix_matching.py
```

**Key Features**:

- Compares baseline (explicit codes only) vs strict/partial/lax prefix matching
- Analyzes primary, secondary, and all diagnosis fields separately
- Identifies inadvertent inclusion due to automatic prefix matching
- Maps affected codelists to GitHub repositories that use them
- Splits results by creation method (Builder/Uploaded/Inline)

**Scenarios Analyzed**:

- **Baseline**: Only codes explicitly in the codelist
- **Strict**: Including EXTRA descendants of COMPLETE codes
- **Partial**: Including EXTRA descendants of COMPLETE and PARTIAL codes
- **Lax** (uploaded only): Including descendants of NONE codes

---

### 4. `create_emails_for_moved_code_repos.py` - GitHub Code Search & Email Generation

**Purpose**: Searches GitHub for ICD-10 codes that have moved between the 2016 and 2019 versions, generating per-repo email notifications. Also integrates prefix matching warnings for codelists with incomplete descendant coverage.

**Inputs**:

- `reporting/swapped_codes.json` - Codes that changed between ICD-10 versions
- `reporting/outputs/code_usage_combined_apcs.csv` - Usage counts for context
- `reporting/outputs/prefix_matching_repos.csv` - Prefix matching warnings per
- GitHub API (requires `gh` CLI authentication)

**Outputs**:

- `reporting/repo_emails/*.md` - Individual email files per affected repository
- `reporting/data/github_code_search_cache.json` - Cached search results

**Run**:

```bash
# First time or to refresh cache
gh auth login
python3 reporting/create_emails_for_moved_code_repos.py --force

# Use cached results
python3 reporting/create_emails_for_moved_code_repos.py
```

**Key Features**:

- Searches all opensafely organization repositories via GitHub API
- Filters false positives (OPCS codes, CTV3 codes, etc.)
- Generates custom messages per code group (G906, K58*, U* codes)
- Includes usage totals and GitHub permalinks with line numbers
- Handles rate limiting with automatic retry
- Caching prevents redundant API calls
- **Integrates prefix matching warnings** - automatically includes ehrQL prefix matching warnings in emails for affected repos
- **Unified emails** - generates a single email with both moved code findings and prefix matching warnings (if applicable) per repository

**Email Content**:

Each generated email may include:

1. **Prefix Matching Warnings** (if applicable):
   - List of codelists with incomplete descendant coverage
   - Explanation of Cohort Extractor vs ehrQL behavior differences
   - Current event counts vs. expected counts with prefix matching
   - Percentage increase to highlight impact
   - Recommendation to review codelists or use explicit prefix matching

2. **Moved Code Findings** (if applicable):
   - Codes that changed between ICD-10 versions
   - File locations with line numbers and GitHub permalinks
   - Usage statistics
   - Custom messages based on code type

### 5. `generate_consolidated_reports.py` - Consolidated Reports Generation

**Purpose**: Generates two consolidated markdown reports summarizing projects affected by ICD-10 code moving and prefix matching issues. Instead of per-repo emails, creates organization-wide reports showing all affected projects and their impacts.

**Inputs**:

- `reporting/swapped_codes.json` - Codes that moved between ICD-10 versions
- `reporting/outputs/code_usage_combined_apcs.csv` - Usage counts (all-time totals for all diagnoses field)
- `reporting/outputs/prefix_matching_repos.csv` - Prefix matching warnings per repo
- `reporting/outputs/codelist_coverage_detail_apcs.csv` - Codelist coverage details
- `reporting/data/github_code_search_cache.json` - Cached GitHub search results (created if not exists)
- GitHub API (requires `gh` CLI authentication)

**Outputs**:

- `reporting/outputs/moved_codes_report.md` - Consolidated report of all projects affected by moved ICD-10 codes
- `reporting/outputs/prefix_matching_report.md` - Consolidated report of all projects affected by prefix matching changes
- `reporting/data/github_code_search_cache.json` - Updated cache of GitHub search results

**Run**:

```bash
# First time or to refresh GitHub search cache
gh auth login
python3 reporting/generate_consolidated_reports.py --force

# Use cached GitHub search results
python3 reporting/generate_consolidated_reports.py
```

**Key Features**:

- **Moved Codes Report**:
  - Searches all opensafely organization repositories for moved codes
  - Groups findings by affected project
  - Shows all-time usage totals from "all diagnoses" field in APCS data
  - Provides context about which ICD-10 edition codes appear in
  - Custom messaging for different code groups (G906, K58*, U* codes)

- **Prefix Matching Report**:
  - Lists projects using codelists with incomplete descendant coverage
  - Shows three scenarios for each affected codelist:
    - **Exact match**: Only codes explicitly in codelist (2024-25 primary diagnosis counts)
    - **With X-padded codes**: Exact codes plus X-padded versions (2024-25 primary diagnosis counts)
    - **With prefix matching**: Including all descendants (2024-25 primary diagnosis counts)
  - Calculates percentage increase to show impact
  - Explains Cohort Extractor vs ehrQL behavioral differences
  - Aggregates totals per project

- **Caching & Rate Limiting**:
  - Caches GitHub API search results to avoid redundant calls
  - Handles GitHub API rate limiting with automatic retry
  - Use `--force` flag to refresh cached search results

**Report Summaries**:

Both reports include:

- Executive summary with count of affected projects
- List of all affected projects
- Detailed breakdowns per project
- Usage statistics and impact metrics

---

## Recommended Execution Order

Run the scripts in this order for a complete analysis:

```bash
# 1. Generate core usage data and identify missing codes
python3 -m reporting.missing_codes

# 2. Analyze codelist coverage (requires output from step 1)
python3 -m reporting.analyze_codelist_coverage

# 3. Analyze prefix matching impact (requires output from step 2)
python3 -m reporting.analyze_prefix_matching

# 4. Generate consolidated reports (requires output from steps 1-3, and gh CLI)
gh auth login  # if not already authenticated
python3 -m reporting.generate_consolidated_reports

# Alternative: Generate per-repo emails instead of consolidated reports
python3 reporting/create_emails_for_moved_code_repos.py
```

## Output Directory Structure

After running all scripts, the `reporting/outputs/` directory will contain:

```
reporting/outputs/
├── code_usage_combined_apcs.csv              # From missing_codes.py
├── code_usage_combined_ons_deaths.csv        # From missing_codes.py
├── codelist_coverage_detail_apcs.csv         # From analyze_codelist_coverage.py
├── codelist_coverage_detail_ons_deaths.csv   # From analyze_codelist_coverage.py
├── ocl_codes_not_in_apcs.csv                 # From missing_codes.py
├── ocl_codes_not_in_ons_deaths.csv           # From missing_codes.py
├── prefix_matching_analysis.csv              # From analyze_prefix_matching.py
├── prefix_matching_analysis.md               # From analyze_prefix_matching.py
├── prefix_matching_repos.csv                 # From analyze_prefix_matching.py
├── moved_codes_report.md                     # From generate_consolidated_reports.py
└── prefix_matching_report.md                 # From generate_consolidated_reports.py
```

## Notes

- Suppressed values (<15) are treated as 0
- The analysis uses the 2019 edition of ICD-10 from OpenCodelists
- APCS data uses a modified 2016 version with some differences from the 2019 edition

## Other scripts

- `reporting/analyze_orphan_codes.py` - Identifies codes that exist in a codelist, but where none of its children do - probably should call this childless rather than orphan.
- `reporting/generate_codelist_issues_report.py` - Check - might be able to remove this
