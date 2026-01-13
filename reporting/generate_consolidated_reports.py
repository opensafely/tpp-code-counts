#!/usr/bin/env python3
"""
Generate consolidated reports for code moving and prefix matching issues.

Instead of per-repo emails, creates two consolidated reports:
1. moved_codes_report.md - All projects affected by code moving
2. prefix_matching_report.md - All projects affected by prefix matching

For prefix matching, also shows the impact if codes ending in 'X' are excluded.

Usage:
    gh auth login  # if not already authenticated
    python reporting/generate_consolidated_reports.py [--force]

    --force: Ignore cache and fetch fresh results from GitHub
"""

import csv
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path


SWAPPED_CODES_FILE = Path(__file__).parent / "swapped_codes.json"
MOVED_CODES_REPORT = Path(__file__).parent / "outputs" / "moved_codes_report.md"
PREFIX_MATCHING_REPORT = Path(__file__).parent / "outputs" / "prefix_matching_report.md"
CACHE_FILE = Path(__file__).parent / "data" / "github_code_search_cache.json"
USAGE_FILE = Path(__file__).parent / "outputs" / "code_usage_combined_apcs.csv"
PREFIX_MATCHING_FILE = Path(__file__).parent / "outputs" / "prefix_matching_repos.csv"
CODELIST_COVERAGE_FILE = (
    Path(__file__).parent / "outputs" / "codelist_coverage_detail_apcs.csv"
)


def run_gh_command(args):
    """Run gh CLI command and return output.

    Args:
        args: List of arguments to pass to gh

    Returns:
        tuple: (success, output) where success is bool and output is str
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check for rate limit in stderr
        if "API rate limit exceeded" in result.stderr:
            print(
                "\n⚠️  GitHub API rate limit exceeded. Waiting 60 seconds before retry..."
            )
            time.sleep(60)
            # Retry once after waiting
            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                timeout=30,
            )

        return result.returncode == 0, result.stdout.strip()
    except FileNotFoundError:
        print("ERROR: gh CLI not found. Please install it: https://cli.github.com")
        return False, ""
    except subprocess.TimeoutExpired:
        return False, ""


def load_cache():
    """Load cached search results.

    Returns:
        dict: {code: {repo: [matches]}}
    """
    if not CACHE_FILE.exists():
        return {}

    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    """Save search results to cache.

    Args:
        cache: dict of {code: {repo: [matches]}}
    """
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except OSError as e:
        print(f"WARNING: Could not save cache: {e}")


def load_usage_totals():
    """Load usage totals per ICD10 code from code_usage_combined_apcs.csv.

    Returns:
        dict: {code: {"total": int}}
    """
    totals = {}
    if not USAGE_FILE.exists():
        print(f"WARNING: Usage file not found: {USAGE_FILE}")
        return totals

    try:
        with open(USAGE_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get("icd10_code") or "").strip().upper()
                fy = (row.get("financial_year") or "").strip()

                if not code:
                    continue

                # Convert counts: numbers as ints; suppressed counts (<15) treated as 0
                try:
                    all_count = int((row.get("apcs_all_count") or "").strip())
                except ValueError:
                    all_count = 0
                try:
                    primary_count = int((row.get("apcs_primary_count") or "").strip())
                except ValueError:
                    primary_count = 0

                entry = totals.setdefault(
                    code, {"all_total": 0, "primary_total": 0, "primary_24_25": 0}
                )
                entry["all_total"] += all_count
                entry["primary_total"] += primary_count
                if fy == "2024-25":
                    entry["primary_24_25"] += primary_count
    except OSError as e:
        print(f"WARNING: Could not read usage file {USAGE_FILE}: {e}")

    return totals


def load_codelist_codes():
    """Load codes for each codelist from codelist_coverage_detail_apcs.csv.

    Returns:
        dict: {codelist_id: [codes]}
    """
    codelist_codes = defaultdict(list)

    if not CODELIST_COVERAGE_FILE.exists():
        print(f"INFO: Codelist coverage file not found at {CODELIST_COVERAGE_FILE}")
        return codelist_codes

    try:
        with open(CODELIST_COVERAGE_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                codelist_id = row.get("codelist_id", "").strip()
                icd10_code = row.get("icd10_code", "").strip()
                status = row.get("status", "").strip()

                if not codelist_id or not icd10_code:
                    continue

                # Only include codes that are in the codelist (COMPLETE, PARTIAL, NONE)
                # Skip EXTRA codes as they're not part of the original codelist
                if status in ("COMPLETE", "PARTIAL", "NONE"):
                    codelist_codes[codelist_id].append(icd10_code)
    except OSError as e:
        print(f"WARNING: Could not read codelist coverage file: {e}")

    return codelist_codes


def calculate_usage_scenarios(usage_totals, codelist_codes):
    """Calculate three usage scenarios for a codelist.

    Args:
        usage_totals: dict of {code: {"primary_24_25": int, "primary_total": int, "all_total": int}} from code_usage_combined_apcs.csv
        codelist_codes: list of codes in the codelist

    Returns:
        tuple: (exact_match, with_prefix, with_x_padding) - event counts for each scenario using primary_24_25 data
    """
    if not codelist_codes:
        return 0, 0, 0

    # Scenario (a): Exact code matches only
    exact_match = sum(
        usage_totals.get(code, {}).get("primary_24_25", 0) for code in codelist_codes
    )

    # Scenario (b): With prefix matching - any code starting with a codelist code
    with_prefix = 0
    counted_codes = set()
    for codelist_code in codelist_codes:
        for usage_code, usage_data in usage_totals.items():
            if usage_code.startswith(codelist_code) and usage_code not in counted_codes:
                with_prefix += usage_data.get("primary_24_25", 0)
                counted_codes.add(usage_code)

    # Scenario (c): With X-padding - exact codes + codes with X suffix
    with_x_padding = exact_match
    for codelist_code in codelist_codes:
        # Add the X-padded version if it exists
        x_code = (
            codelist_code + "X" if not codelist_code.endswith("X") else codelist_code
        )
        if x_code in usage_totals:
            with_x_padding += usage_totals[x_code].get("primary_24_25", 0)

    return exact_match, with_prefix, with_x_padding


def load_prefix_matching_warnings():
    """Load prefix matching warnings per repo from prefix_matching_repos.csv.

    Returns:
        dict: {repo: [{"codelist": str, "current": int, "with_prefix": int}]}
    """
    warnings = defaultdict(list)

    if not PREFIX_MATCHING_FILE.exists():
        print(
            f"INFO: Prefix matching file not found at {PREFIX_MATCHING_FILE}, skipping prefix matching warnings"
        )
        return warnings

    try:
        with open(PREFIX_MATCHING_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                repo = row.get("repo", "").strip()
                codelist = row.get("codelist", "").strip()
                current = row.get("current_event_count", "0").strip()
                with_prefix = row.get("event_count_with_prefix_matching", "0").strip()

                # Skip repos marked as not found
                if repo == "(not found in repos)" or not repo:
                    continue

                # Remove opensafely/ prefix if present
                if repo.startswith("opensafely/"):
                    repo = repo.replace("opensafely/", "")

                # Parse numbers for filtering
                try:
                    current_num = int(current)
                    with_prefix_num = int(with_prefix)
                except ValueError:
                    current_num = 0
                    with_prefix_num = 0

                warnings[repo].append(
                    {
                        "codelist": codelist,
                        "current": current_num,
                        "with_prefix": with_prefix_num,
                        "current_str": current,
                        "with_prefix_str": with_prefix,
                    }
                )
    except OSError as e:
        print(
            f"WARNING: Could not read prefix matching file {PREFIX_MATCHING_FILE}: {e}"
        )

    return warnings


def should_exclude_line(line, path):
    """Check if a line should be excluded based on filtering rules.

    Args:
        line: The line of code to check
        path: The file path

    Returns:
        bool: True if the line should be excluded, False otherwise
    """
    # Rule 1: Exclude if line contains "U12 small nuclear mutation"
    if "U12 small nuclear mutation" in line:
        return True

    # Rule 2: Exclude if line starts with "U***,Unspecified diagnostic imaging"
    # where * is a numeric character
    if re.match(r"^U\d\d\d,Unspecified diagnostic imaging", line):
        return True

    # Rule 3: Exclude if filename contains "opcs" (case-insensitive)
    if "opcs" in path.lower():
        return True

    # Rule 4: Exclude if code line is like "K58*,Percutaneous"
    if re.match(r"^K58\d,Percutaneous", line):
        return True

    # Rule 5: Exclude U10 - Falls as that is CTV3, not ICD10
    if re.match(r"^U10.*Falls", line):
        return True

    # Rule 6: Exclude K588 - Other specified diagnostic transluminal operations
    if re.match(r"^K588,Other specified diagnostic transluminal operations", line):
        return True

    return False


def search_code_in_org(code):
    """Search for a code in all opensafely repos with a single API call.

    Args:
        code: ICD-10 code to search for

    Returns:
        dict: {repo_name: [matching_lines]}
    """
    results = defaultdict(list)

    print(f"  Searching for {code}...", end="", flush=True)

    # Construct the query: "CODE" org:opensafely
    query = f'"{code}"+org:opensafely'

    success, output = run_gh_command(
        [
            "api",
            "-H",
            "Accept: application/vnd.github.text-match+json",
            f"/search/code?q={query}",
        ]
    )

    if not success:
        print(" ERROR: API call failed")
        return results

    if success and output:
        try:
            data = json.loads(output)

            # Check for rate limit error
            if "message" in data and "rate limit" in data["message"].lower():
                print(" RATE LIMITED")
                return results

            items = data.get("items", [])

            for item in items:
                path = item.get("path", "")
                repo_full_name = item.get("repository", {}).get("full_name", "")

                # Extract line text from text_matches
                line_texts = []
                text_matches = item.get("text_matches", [])
                if text_matches:
                    for match in text_matches:
                        fragment = match.get("fragment", "")
                        if fragment:
                            # Split fragment into lines and find lines containing the code
                            lines = fragment.split("\n")
                            for line in lines:
                                # Check if this line contains the exact code we're searching for
                                # Look for the code as a distinct word (capital letters/numbers)
                                if re.search(r"\b" + re.escape(code) + r"\b", line):
                                    # Strip whitespace and only add if not empty
                                    clean_line = line.strip()
                                    if clean_line:
                                        # Apply filtering rules to exclude false positives
                                        if should_exclude_line(clean_line, path):
                                            continue
                                        line_texts.append(clean_line)

                # If no matching lines found, skip this match
                if not line_texts:
                    continue

                # Extract just the repo name from opensafely/repo-name format
                if repo_full_name.startswith("opensafely/"):
                    repo = repo_full_name.replace("opensafely/", "")
                else:
                    repo = repo_full_name

                if path and repo:
                    # Remove duplicates while preserving order
                    seen = set()
                    for line_text in line_texts:
                        if line_text not in seen:
                            seen.add(line_text)
                            results[repo].append(
                                {
                                    "path": path,
                                    "line_text": line_text,
                                }
                            )
        except json.JSONDecodeError:
            pass

    found_count = len(results)
    if found_count > 0:
        total_matches = sum(len(matches) for matches in results.values())
        print(f" found in {found_count} repo(s) ({total_matches} matches)")
    else:
        print(" (no results)")

    # Convert defaultdict to regular dict for JSON serialization
    return dict(results)


def load_codes():
    """Load codes from swapped_codes.json.

    Returns:
        tuple: (codes_dict, groups_list)
            codes_dict: {code: description, ...}
            groups_list: [{"codes": [...], "description": "..."}, ...]
    """
    if not SWAPPED_CODES_FILE.exists():
        print(f"ERROR: {SWAPPED_CODES_FILE} not found")
        return {}, []

    try:
        with open(SWAPPED_CODES_FILE) as f:
            data = json.load(f)

        codes = {}
        # Expected format: [{"codes": [...], "description": "..."}, ...]
        for entry in data:
            description = entry.get("description", "")
            for code in entry.get("codes", []):
                codes[code] = description

        print(f"Loaded {len(codes)} unique codes from swapped_codes.json\n")
        return codes, data
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR loading codes: {e}")
        return {}, []


def generate_moved_codes_report(all_results, codes, groups, usage_totals):
    """Generate consolidated report for projects affected by code moving."""

    # Aggregate all results by repo and file
    repo_file_matches = defaultdict(lambda: defaultdict(list))

    for code in all_results:
        for repo, matches in all_results[code].items():
            for match in matches:
                path = match["path"]
                line_text = match["line_text"]
                repo_file_matches[repo][path].append(
                    {
                        "code": code,
                        "line": line_text,
                        "description": codes.get(code, ""),
                    }
                )

    # Filter repos that have at least one code match
    affected_repos = sorted(repo_file_matches.keys())

    if not affected_repos:
        print("No projects found with moved codes")
        return

    report_lines = []
    report_lines.append("# Moved ICD-10 Codes Report")
    report_lines.append("")
    report_lines.append(
        f"**Generated**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    report_lines.append("")
    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append(
        f"**{len(affected_repos)} projects** are affected by ICD-10 code movement between different editions."
    )
    report_lines.append("")
    report_lines.append("### Affected Projects:")
    report_lines.append("")
    for repo in affected_repos:
        report_lines.append(f"- `{repo}`")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Generate details for each repo
    for repo in affected_repos:
        files_by_path = repo_file_matches[repo]

        # Collect codes present in this repo
        repo_codes = set()
        for file_matches in files_by_path.values():
            for match in file_matches:
                repo_codes.add(match["code"])

        report_lines.append(f"## {repo}")
        report_lines.append("")

        # Generate group summaries
        for group in groups:
            group_codes = group.get("codes", [])
            description = group.get("description", "")
            actual_codes = group.get("actual_codes", [])
            present = sorted(set(group_codes) & repo_codes)
            if not present:
                continue

            header_codes = ", ".join(present)

            # Compose usage phrase for actual codes
            usage_phrases = []
            for ac in actual_codes:
                entry = usage_totals.get(ac, {"all_total": 0})
                usage_phrases.append(
                    f"{ac} has occurred {entry.get('all_total', 0)} times"
                )
            usage_text = "; ".join(usage_phrases)

            # Singular/plural wording
            plural_present = len(present) != 1
            plural_actual = len(actual_codes) != 1
            subject = "These codes" if plural_present else "This code"
            verb_appear = "appear" if plural_present else "appears"
            verb_use = "use" if plural_present else "uses"
            actual_word = "codes" if plural_actual else "code"
            actual_codes_str = ", ".join(actual_codes)

            # Custom phrasing per code group
            is_g906 = "G906" in group_codes
            is_k58_group = any(c.startswith("K58") for c in group_codes)
            is_u_group = all(c.startswith("U") for c in group_codes)

            if is_g906:
                report_lines.append(
                    f"**{header_codes}** - {description}: "
                    f"{subject} {verb_appear} in the 2019 edition of ICD10, "
                    f"but {verb_use} the older 2016 {actual_word} ({actual_codes_str}) in HES APCS data. "
                    f"{usage_text}.\n"
                )
            elif is_k58_group:
                report_lines.append(
                    f"**{header_codes}** - {description}: "
                    f"{subject} {verb_appear} in the 2019 edition of ICD10, "
                    f"but {verb_use} the older 2016 {actual_word} ({actual_codes_str}) in HES APCS data. "
                    f"{usage_text}.\n"
                )
            elif is_u_group:
                report_lines.append(
                    f"**{header_codes}** - {description}: "
                    f"{subject} {verb_appear} in the 2019 edition of ICD10, "
                    f"and in the ONS deaths data, but {verb_use} the older 2016 {actual_word} "
                    f"({actual_codes_str}) in the HES APCS data. {usage_text}.\n"
                )
            else:
                appear_as = "appear" if plural_present else "appears"
                report_lines.append(
                    f"**{header_codes}** - {description}: "
                    f"{subject} {verb_appear} in the ONS deaths data, "
                    f"but {appear_as} as {actual_codes_str} in HES APCS data. {usage_text}.\n"
                )

        report_lines.append("")

    # Write report
    try:
        with open(MOVED_CODES_REPORT, "w") as f:
            f.write("\n".join(report_lines))
        print(f"✓ Moved codes report written to {MOVED_CODES_REPORT}")
    except OSError as e:
        print(f"ERROR: Could not write moved codes report: {e}")


def generate_prefix_matching_report(prefix_warnings, usage_totals, codelist_codes):
    """Generate consolidated report for projects affected by prefix matching.

    Args:
        prefix_warnings: dict of {repo: [warnings]}
        usage_totals: dict of {code: {"total": int}}
        codelist_codes: dict of {codelist_id: [codes]}
    """

    if not prefix_warnings:
        print("No projects found with prefix matching issues")
        return

    affected_repos = sorted(prefix_warnings.keys())

    report_lines = []
    report_lines.append("# Prefix Matching Issues Report")
    report_lines.append("")
    report_lines.append(
        f"**Generated**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    report_lines.append("")
    report_lines.append(
        "## ⚠️  Prefix Matching Changes Between Cohort Extractor and ehrQL"
    )
    report_lines.append("")
    report_lines.append(
        "In Cohort Extractor (the old framework), prefix matching was applied by default when "
        "querying the primary and secondary diagnosis fields in HES APCS data. This means that "
        "a code like `E10` would automatically match `E10`, `E100`, `E101`, `E102`, etc."
    )
    report_lines.append("")
    report_lines.append(
        "**In ehrQL, prefix matching is NOT automatically applied to these fields.** "
    )
    report_lines.append("")
    report_lines.append(
        "There are two sources of potential error from this:\n"
        "1. 3-character ICD10 codes get padded with an X in hospital data - so A33 becomes A33X in the data\n"
        "2. Some 4 character ICD10 codes have an optional 5th character modifier"
    )
    report_lines.append("")
    report_lines.append(
        "For each affected project and each affected codelist, this report shows "
        "how many primary diagnosis events, in the 24/25 financial year, would be matched under three scenarios:\n"
        "1. Just using the codes in the codelist\n"
        "2. Using the codes in the codelist AND any 'X'-padded codes\n"
        "3. Match any code that starts with a codelist code (i.e., prefix matching)"
    )
    report_lines.append("")
    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append(
        f"**{len(affected_repos)} projects** may be affected by this change."
    )
    report_lines.append("")
    report_lines.append("### Affected Projects:")
    report_lines.append("")
    for repo in affected_repos:
        report_lines.append(f"- `{repo}`")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Generate details for each repo
    for repo in affected_repos:
        warnings = prefix_warnings[repo]

        report_lines.append(f"## {repo}")
        report_lines.append("")
        report_lines.append("### Affected Codelists:")
        report_lines.append("")

        total_exact = 0
        total_with_prefix = 0
        total_with_x = 0

        for warning in warnings:
            codelist = warning["codelist"]

            # Get codes for this codelist
            codes = codelist_codes.get(codelist, [])

            # Calculate the three scenarios
            exact, with_prefix, with_x = calculate_usage_scenarios(usage_totals, codes)

            total_exact += exact
            total_with_prefix += with_prefix
            total_with_x += with_x

            report_lines.append(f"- **`{codelist}`**")
            report_lines.append(f"  - Just the codelist: {exact:,}")

            if exact > 0:
                pct_prefix = ((with_prefix - exact) / exact) * 100
                pct_x = ((with_x - exact) / exact) * 100
                report_lines.append(
                    f"  - With X-padded codes: {with_x:,} ({pct_x:.0f}% increase)"
                )
                report_lines.append(
                    f"  - With prefix matching: {with_prefix:,} ({pct_prefix:.0f}% increase)"
                )
            else:
                report_lines.append(f"  - With X-padded codes: {with_x:,}")
                report_lines.append(f"  - With prefix matching: {with_prefix:,}")

        report_lines.append("")
        report_lines.append(f"**Total for {repo}:**")
        report_lines.append(f"- Exact match: {total_exact:,} events")
        report_lines.append(f"- With X-padded codes: {total_with_x:,} events")
        report_lines.append(f"- With prefix matching: {total_with_prefix:,} events")
        report_lines.append("")

    # Write report
    try:
        with open(PREFIX_MATCHING_REPORT, "w") as f:
            f.write("\n".join(report_lines))
        print(f"✓ Prefix matching report written to {PREFIX_MATCHING_REPORT}")
    except OSError as e:
        print(f"ERROR: Could not write prefix matching report: {e}")


def main():
    """Main entry point."""
    # Check for --force flag
    force = "--force" in sys.argv

    # Check if gh CLI is available
    success, output = run_gh_command(["--version"])
    if not success:
        print("ERROR: gh CLI not installed")
        print("\nSetup instructions:")
        print("1. Install gh CLI: https://cli.github.com")
        print("2. Authenticate: gh auth login")
        print("3. Run this script again")
        sys.exit(1)

    codes, groups = load_codes()
    if not codes:
        sys.exit(1)

    # Load cache
    cache = {} if force else load_cache()
    if cache and not force:
        print(f"Loaded {len(cache)} cached results (use --force to refresh)\n")

    print(f"Searching opensafely org for {len(codes)} codes...\n")

    all_results = {}
    codes_to_search = []

    # Check which codes need to be searched
    for code in sorted(codes.keys()):
        if code in cache and not force:
            all_results[code] = cache[code]
            print(f"  {code}: using cached results")
        else:
            codes_to_search.append(code)

    # Search for codes not in cache
    if codes_to_search:
        print(f"\nFetching {len(codes_to_search)} code(s) from GitHub...\n")
        for i, code in enumerate(codes_to_search):
            all_results[code] = search_code_in_org(code)
            # Add delay between searches to avoid rate limiting
            if i < len(codes_to_search) - 1:
                time.sleep(2)

        # Save updated cache
        save_cache(all_results)
        print(f"\nCache saved to {CACHE_FILE}")

    usage_totals = load_usage_totals()
    prefix_warnings = load_prefix_matching_warnings()
    codelist_codes = load_codelist_codes()

    print()
    generate_moved_codes_report(all_results, codes, groups, usage_totals)
    generate_prefix_matching_report(prefix_warnings, usage_totals, codelist_codes)

    print(f"\n✓ Reports generated in {Path(__file__).parent / 'outputs'}/")


if __name__ == "__main__":
    main()
