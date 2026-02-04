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
import sys
from collections import defaultdict

from .common import (
    DATA_DIR,
    OUT_DIR,
    find_all_codes_in_github,
    get_apcs_coverage_data,
    load_prefix_matching_warnings,
    load_swapped_codes,
    load_usage_data,
)


MOVED_CODES_REPORT = OUT_DIR / "moved_codes_report.md"
PREFIX_MATCHING_REPORT = OUT_DIR / "prefix_matching_report.md"
REPO_PROJECT_NUMBER_FILE = DATA_DIR / "repo_projectnumber.csv"


def load_repo_project_numbers():
    """Load repo to project number mapping from CSV.

    Returns:
        dict: {repo_name: {"number": str, "name": str, "slug": str, "url": str}}
    """
    repo_project_map = {}

    if not REPO_PROJECT_NUMBER_FILE.exists():
        print(f"INFO: Repo project number file not found at {REPO_PROJECT_NUMBER_FILE}")
        return repo_project_map

    try:
        with open(REPO_PROJECT_NUMBER_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                number = row.get("number", "").strip()
                name = row.get("name", "").strip()
                slug = row.get("slug", "").strip()
                url = row.get("url", "").strip()

                if url:
                    # Extract repo name from URL (e.g., "repo-name" from URL)
                    # URLs are like: https://github.com/opensafely/repo-name
                    if "github.com/opensafely/" in url:
                        repo_name = url.split("github.com/opensafely/")[1].rstrip("/")
                        repo_project_map[repo_name] = {
                            "number": number if number else "",
                            "name": name if name else "",
                            "slug": slug if slug else "",
                            "url": url,
                        }
    except OSError as e:
        print(f"WARNING: Could not read repo project number file: {e}")

    return repo_project_map


def calculate_usage_scenarios(usage_totals, codelist_codes):
    """Calculate three usage scenarios for a codelist.

    Args:
        usage_totals: dict of {code: {("apcs_primary_count", "24-25"): int}}
        codelist_codes: list of codes in the codelist

    Returns:
        tuple: (exact_match, with_prefix, with_x_padding) - event counts for each scenario using primary_24_25 data
    """
    if not codelist_codes:
        return 0, 0, 0

    # Scenario (a): Exact code matches only
    exact_match = sum(
        usage_totals.get(code, {}).get(("apcs_primary_count", "2024-25"), 0)
        for code in codelist_codes
    )

    # Scenario (b): With prefix matching - any code starting with a codelist code
    with_prefix = 0
    counted_codes = set()
    for codelist_code in codelist_codes:
        for usage_code, usage_data in usage_totals.items():
            if usage_code.startswith(codelist_code) and usage_code not in counted_codes:
                with_prefix += usage_data.get(("apcs_primary_count", "2024-25"), 0)
                counted_codes.add(usage_code)

    # Scenario (c): With X-padding - exact codes + codes with X suffix
    with_x_padding = exact_match
    for codelist_code in codelist_codes:
        # Add the X-padded version if it exists
        x_code = (
            codelist_code + "X" if not codelist_code.endswith("X") else codelist_code
        )
        if x_code in usage_totals:
            with_x_padding += usage_totals[x_code].get(
                ("apcs_primary_count", "2024-25"), 0
            )

    return exact_match, with_prefix, with_x_padding


def generate_moved_codes_report(
    all_results, codes, groups, usage_totals, repo_project_map
):
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

    # Create markdown table with project number, name, and repo
    report_lines.append("| Project # | Project Name | Repository |")
    report_lines.append("|-----------|-------------|-----------|")
    for repo in affected_repos:
        repo_info = repo_project_map.get(repo, {})
        project_num = repo_info.get("number", "")
        project_name = repo_info.get("name", "")
        project_slug = repo_info.get("slug", "")
        github_url = f"https://github.com/opensafely/{repo}"

        # Format project name as link if slug exists
        if project_slug and project_name:
            name_cell = f"[{project_name}](https://jobs.opensafely.org/{project_slug})"
        elif project_name:
            name_cell = project_name
        else:
            name_cell = ""

        # Format repo as link to GitHub
        repo_cell = f"[{repo}]({github_url})"

        report_lines.append(f"| {project_num} | {name_cell} | {repo_cell} |")

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
                entry = usage_totals.get(ac, {("apcs_all_count", "TOTAL"): 0})
                usage_phrases.append(
                    f"{ac} has occurred {entry.get(('apcs_all_count', 'TOTAL'), 0)} times"
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


def generate_prefix_matching_report(
    prefix_warnings, usage_totals, codelist_codes, repo_project_map
):
    """Generate consolidated report for projects affected by prefix matching.

    Args:
        prefix_warnings: dict of {repo: [warnings]}
        usage_totals: dict of {code: {"total": int}}
        codelist_codes: dict of {codelist_id: [codes]}
        repo_project_map: dict of {repo: project_number}
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

    # Create markdown table with project number, name, and repo
    report_lines.append("| Project # | Project Name | Repository |")
    report_lines.append("|-----------|-------------|-----------|")
    for repo in affected_repos:
        repo_info = repo_project_map.get(repo, {})
        project_num = repo_info.get("number", "")
        project_name = repo_info.get("name", "")
        project_slug = repo_info.get("slug", "")
        github_url = f"https://github.com/opensafely/{repo}"

        # Format project name as link if slug exists
        if project_slug and project_name:
            name_cell = f"[{project_name}](https://jobs.opensafely.org/{project_slug})"
        elif project_name:
            name_cell = project_name
        else:
            name_cell = ""

        # Format repo as link to GitHub
        repo_cell = f"[{repo}]({github_url})"

        report_lines.append(f"| {project_num} | {name_cell} | {repo_cell} |")

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

    codes, groups = load_swapped_codes()
    if not codes:
        sys.exit(1)

    all_results = find_all_codes_in_github(set(codes.keys()), force)
    usage_totals, _ = load_usage_data("apcs")
    prefix_warnings = load_prefix_matching_warnings()
    _, codelist_codes = get_apcs_coverage_data()
    repo_project_map = load_repo_project_numbers()

    print()
    generate_moved_codes_report(
        all_results, codes, groups, usage_totals, repo_project_map
    )
    generate_prefix_matching_report(
        prefix_warnings, usage_totals, codelist_codes, repo_project_map
    )

    print(f"\n✓ Reports generated in {OUT_DIR}/")


if __name__ == "__main__":
    main()
