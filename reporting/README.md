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
python3 reporting/missing_codes.py
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
python3 reporting/analyze_codelist_coverage.py
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

### 4. `create_emails_for_moved_code_repos.py` - GitHub Code Search

**Purpose**: Searches GitHub for ICD-10 codes that have moved between the 2016 and 2019 versions, generating per-repo email notifications.

**Inputs**:

- `reporting/swapped_codes.json` - Codes that changed between ICD-10 versions
- `reporting/outputs/code_usage_combined_apcs.csv` - Usage counts for context
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

---

## Recommended Execution Order

Run the scripts in this order for a complete analysis:

```bash
# 1. Generate core usage data and identify missing codes
python3 reporting/missing_codes.py

# 2. Analyze codelist coverage (requires output from step 1)
python3 reporting/analyze_codelist_coverage.py

# 3. Analyze prefix matching impact (requires output from step 2)
python3 reporting/analyze_prefix_matching.py

# 4. Search GitHub for moved codes (optional, requires gh CLI)
gh auth login  # if not already authenticated
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
└── prefix_matching_repos.csv                 # From analyze_prefix_matching.py
```

## Notes

- Suppressed values (<15) are treated as 0
- The analysis uses the 2019 edition of ICD-10 from OpenCodelists
- APCS data uses a modified 2016 version with some differences from the 2019 edition
