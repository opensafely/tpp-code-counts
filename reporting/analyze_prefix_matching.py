#!/usr/bin/env python3
"""
This script:
1. Analyzes how different prefix matching assumptions affect event counts for codelists
2. Maps codelists with discrepancies to GitHub repos that use them

Comparing scenarios:
- Baseline: Only codes explicitly in the codelist
- Strict: Including EXTRA descendants of COMPLETE codes
- Partial: Including EXTRA descendants of COMPLETE and PARTIAL codes
- NONE (uploaded only): Including descendants of NONE codes

For the all_count field, it analyzes the impact of inadvertent inclusion
of PARTIAL code descendants due to automatic prefix matching.

Usage:
    python analyze_prefix_matching.py
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


# Paths
REPO_ROOT = Path(__file__).parent.parent
OUT_DIR = REPO_ROOT / "reporting" / "outputs"
INPUT_FILE = OUT_DIR / "codelist_coverage_detail_apcs.csv"
OUTPUT_CSV = OUT_DIR / "prefix_matching_analysis.csv"
OUTPUT_MD = OUT_DIR / "prefix_matching_analysis.md"
EHRQL_JSON_FILE = REPO_ROOT / "reporting" / "data" / "ehrql_codelists.json"
REPOS_OUTPUT_FILE = OUT_DIR / "prefix_matching_repos.csv"


# ============================================================================
# Stage 1: Analysis Functions
# ============================================================================


def parse_count(value):
    """Parse a count value, treating '<15' as 0."""
    if not value or value.startswith("<"):
        return 0
    return int(value)


def is_descendant(child, parent):
    """Check if child is a descendant of parent code."""
    return child.startswith(parent) and len(child) > len(parent)


def load_coverage_data():
    """Load the codelist coverage detail CSV."""
    data = []
    with open(INPUT_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def get_codelist_codes(data, codelist_id):
    """Get all rows for a specific codelist."""
    return [row for row in data if row["codelist_id"] == codelist_id]


def analyze_primary_secondary(codelist_rows):
    """
    Analyze primary and secondary counts under different scenarios.

    Returns dict with keys:
    - baseline_primary, baseline_secondary
    - strict_primary, strict_secondary
    - partial_primary, partial_secondary
    """
    # Separate codes by status
    codelist_codes = [
        r for r in codelist_rows if r["status"] in ["COMPLETE", "PARTIAL", "NONE"]
    ]
    extra_codes = [r for r in codelist_rows if r["status"] == "EXTRA"]

    # Baseline: only codelist codes
    baseline_primary = sum(parse_count(r["apcs_primary_count"]) for r in codelist_codes)
    baseline_secondary = sum(
        parse_count(r["apcs_secondary_count"]) for r in codelist_codes
    )

    # Build sets of codes by status
    complete_codes = {
        r["icd10_code"] for r in codelist_codes if r["status"] == "COMPLETE"
    }
    partial_codes = {
        r["icd10_code"] for r in codelist_codes if r["status"] == "PARTIAL"
    }

    # Strict: Include EXTRA descendants of COMPLETE codes
    # - 4-char COMPLETE codes: include 5+ char EXTRA children
    # - 3-char COMPLETE codes: include 4-char EXTRA children + their 5+ char EXTRA children
    strict_extra_primary = 0
    strict_extra_secondary = 0

    for extra_row in extra_codes:
        extra_code = extra_row["icd10_code"]

        for complete_code in complete_codes:
            if is_descendant(extra_code, complete_code):
                # Check conditions
                if len(complete_code) == 4 and len(extra_code) >= 5:
                    # 4-char COMPLETE: include 5+ char EXTRA
                    strict_extra_primary += parse_count(extra_row["apcs_primary_count"])
                    strict_extra_secondary += parse_count(
                        extra_row["apcs_secondary_count"]
                    )
                    break
                elif len(complete_code) == 3:
                    # 3-char COMPLETE: include 4-char EXTRA + 5+ char EXTRA
                    strict_extra_primary += parse_count(extra_row["apcs_primary_count"])
                    strict_extra_secondary += parse_count(
                        extra_row["apcs_secondary_count"]
                    )
                    break

    strict_primary = baseline_primary + strict_extra_primary
    strict_secondary = baseline_secondary + strict_extra_secondary

    # Partial: Include EXTRA descendants of COMPLETE and PARTIAL codes
    partial_extra_primary = 0
    partial_extra_secondary = 0

    for extra_row in extra_codes:
        extra_code = extra_row["icd10_code"]

        # Check COMPLETE codes (same as strict)
        for complete_code in complete_codes:
            if is_descendant(extra_code, complete_code):
                if len(complete_code) == 4 and len(extra_code) >= 5:
                    partial_extra_primary += parse_count(
                        extra_row["apcs_primary_count"]
                    )
                    partial_extra_secondary += parse_count(
                        extra_row["apcs_secondary_count"]
                    )
                    break
                elif len(complete_code) == 3:
                    partial_extra_primary += parse_count(
                        extra_row["apcs_primary_count"]
                    )
                    partial_extra_secondary += parse_count(
                        extra_row["apcs_secondary_count"]
                    )
                    break
        else:
            # Check PARTIAL codes (only if not already counted under COMPLETE)
            for partial_code in partial_codes:
                if is_descendant(extra_code, partial_code):
                    if len(partial_code) == 3:
                        # 3-char PARTIAL: include 4-char EXTRA + 5+ char EXTRA
                        partial_extra_primary += parse_count(
                            extra_row["apcs_primary_count"]
                        )
                        partial_extra_secondary += parse_count(
                            extra_row["apcs_secondary_count"]
                        )
                        break

    partial_primary = baseline_primary + partial_extra_primary
    partial_secondary = baseline_secondary + partial_extra_secondary

    return {
        "baseline_primary": baseline_primary,
        "baseline_secondary": baseline_secondary,
        "strict_primary": strict_primary,
        "strict_secondary": strict_secondary,
        "partial_primary": partial_primary,
        "partial_secondary": partial_secondary,
    }


def analyze_none_uploaded(codelist_rows):
    """
    Analyze counts when including descendants of NONE codes (uploaded only).

    Returns dict with keys:
    - none_primary, none_secondary
    """
    codelist_codes = [
        r for r in codelist_rows if r["status"] in ["COMPLETE", "PARTIAL", "NONE"]
    ]
    extra_codes = [r for r in codelist_rows if r["status"] == "EXTRA"]

    # Get NONE codes
    none_codes = {r["icd10_code"] for r in codelist_codes if r["status"] == "NONE"}

    # Include EXTRA descendants of NONE codes
    none_extra_primary = 0
    none_extra_secondary = 0

    for extra_row in extra_codes:
        extra_code = extra_row["icd10_code"]

        for none_code in none_codes:
            if is_descendant(extra_code, none_code) and len(none_code) == 3:
                # 3-char NONE: include 4-char EXTRA + 5+ char EXTRA
                none_extra_primary += parse_count(extra_row["apcs_primary_count"])
                none_extra_secondary += parse_count(extra_row["apcs_secondary_count"])
                break

    return {
        "none_primary": none_extra_primary,
        "none_secondary": none_extra_secondary,
    }


def analyze_all_count(codelist_rows):
    """
    Analyze all_count field impact of prefix matching.

    Returns dict with keys:
    - baseline_all: COMPLETE + PARTIAL + NONE codes
    - with_partial_children_all: baseline + EXTRA children of PARTIAL codes
    """
    codelist_codes = [
        r for r in codelist_rows if r["status"] in ["COMPLETE", "PARTIAL", "NONE"]
    ]
    extra_codes = [r for r in codelist_rows if r["status"] == "EXTRA"]

    # Baseline: only codelist codes
    baseline_all = sum(parse_count(r["apcs_all_count"]) for r in codelist_codes)

    # Get PARTIAL codes
    partial_codes = {
        r["icd10_code"] for r in codelist_codes if r["status"] == "PARTIAL"
    }

    # Include EXTRA descendants of PARTIAL codes
    partial_children_all = 0

    for extra_row in extra_codes:
        extra_code = extra_row["icd10_code"]

        for partial_code in partial_codes:
            if is_descendant(extra_code, partial_code):
                partial_children_all += parse_count(extra_row["apcs_all_count"])
                break

    return {
        "baseline_all": baseline_all,
        "with_partial_children_all": baseline_all + partial_children_all,
    }


def run_analysis():
    """Run the prefix matching analysis and generate outputs."""
    print("Loading data...")
    data = load_coverage_data()

    # Group by codelist
    codelists = {}
    for row in data:
        codelist_id = row["codelist_id"]
        if codelist_id not in codelists:
            codelists[codelist_id] = {
                "creation_method": row["creation_method"],
                "rows": [],
            }
        codelists[codelist_id]["rows"].append(row)

    print(f"Found {len(codelists)} codelists")

    # Analyze each codelist
    results = []

    for codelist_id, info in codelists.items():
        rows = info["rows"]
        creation_method = info["creation_method"]

        # Primary/Secondary analysis
        ps_analysis = analyze_primary_secondary(rows)

        # NONE analysis (only for uploaded)
        none_analysis = {"none_primary": 0, "none_secondary": 0}
        if creation_method == "Uploaded":
            none_analysis = analyze_none_uploaded(rows)

        # All count analysis
        all_analysis = analyze_all_count(rows)

        result = {
            "codelist_id": codelist_id,
            "creation_method": creation_method,
            **ps_analysis,
            **none_analysis,
            **all_analysis,
        }
        results.append(result)

    # Write CSV
    print(f"Writing CSV to {OUTPUT_CSV}...")
    fieldnames = [
        "codelist_id",
        "creation_method",
        "baseline_primary",
        "strict_primary",
        "partial_primary",
        "none_primary",
        "baseline_secondary",
        "strict_secondary",
        "partial_secondary",
        "none_secondary",
        "baseline_all",
        "with_partial_children_all",
    ]

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Generate summary statistics
    print(f"Writing markdown report to {OUTPUT_MD}...")
    write_markdown_report(results)

    print("Done with analysis!")
    return results


def write_markdown_report(results):
    """Write a markdown summary report."""
    # Split by creation method
    builder_results = [r for r in results if r["creation_method"] == "Builder"]
    uploaded_results = [r for r in results if r["creation_method"] == "Uploaded"]
    inline_results = [r for r in results if r["creation_method"] == "Inline"]

    with open(OUTPUT_MD, "w") as f:
        f.write("# APCS missing ICD10 code analysis\n\n")
        f.write(
            "Analysis of how different prefix matching assumptions affect codelist coverage.\n\n"
        )

        f.write("## Introduction\n\n")
        f.write(
            "ICD10 codes appear in the admitted patient care spells (APCS) "
            "table in three fields: primary diagnosis, secondary diagnosis, "
            "and all diagnosis. We ran a "
            "[job](https://jobs.opensafely.org/opensafely-internal/tpp-code-counts/) "
            "to find the usage of all ICD10 codes in APCS. OpenCodelists does "
            "not have all ICD10 codes in its database - partly down to using "
            "the 2019 version of ICD10 (rather than the modified 2016 version "
            "used by APCS), and partly due to the absence of 5 character codes. "
            "This report analyzes to what extent this affects the codelists that "
            "have been used in OpenCodelists.\n\n"
        )

        # Overall summary
        f.write("## Overall Summary\n\n")
        f.write(f"- Total codelists analyzed: {len(results)}\n")
        f.write(f"- Builder codelists: {len(builder_results)}\n")
        f.write(f"- Uploaded codelists: {len(uploaded_results)}\n")
        f.write(f"- Inline codelists: {len(inline_results)}\n\n")
        f.write(
            "A 'builder' codelist is one created using the OpenCodelists builder tool, "
            "whereas an 'uploaded' codelist is one uploaded directly by a user. "
            "'Inline' codelists are hardcoded values in analysis code. They "
            "are reported separately in places because in the builder, children of included codes get "
            "automatically included (unless explicitly excluded), whereas in uploaded and inline codelists they are deliberately excluded.\n\n"
        )

        f.write("## Primary diagnosis field\n\n")
        f.write(
            "This field contains a single ICD10 code. It is ALWAYS 4 or 5 "
            "characters long, with any 3 character codes padded with an X "
            "to make them 4 characters (e.g. `G35` becomes `G35X`).\n\n"
            "Prefix matching is NOT applied by ehrQL when querying this field.\n\n"
            "For our analysis we report:\n"
            "|Strategy|Description|\n"
            "|----|----|\n"
            "|Baseline| Total event count in this field using just codes in the codelist|\n"
            "|Strict| Total event count if we supplement the codelist with the descendants of `COMPLETE`**\\*** codes from the codelist|\n"
            "|Partial| Total event count if we supplement the codelist with the descendants of `COMPLETE`**\\*** and `PARTIAL`**\\*** codes from the codelist|\n"
            "|Lax (uploaded only)| Including descendants of `NONE`**\\*** codes from the codelist|\n\n"
            "**\\*** _For each code in a codelist we look to see whether its "
            "descendants (according to the opencodelist dictionary) are also "
            "present. If all of its descendants are there we class the code as "
            "`COMPLETE`. If some, but not all, we class it as `PARTIAL`. If "
            "none, we class it as `NONE`. NB a code with no children is `COMPLETE`._\n\n"
        )

        # Primary counts analysis
        write_scenario_table(f, results, "primary")

        f.write("### Unaffected Codelists\n\n")
        write_unaffected_table(
            f,
            results,
            builder_results,
            uploaded_results,
            field="primary",
            comparisons=[
                ("Strict vs Baseline", "strict_primary"),
                ("Partial vs Baseline", "partial_primary"),
            ],
        )

        f.write("\n### By Creation Method\n\n")
        f.write("#### Builder Codelists\n\n")
        write_scenario_table(f, builder_results, "primary")

        f.write("\n#### Uploaded Codelists\n\n")
        write_uploaded_scenario_table(f, uploaded_results, "primary")
        write_unaffected_table(
            f,
            uploaded_results,
            builder_results=None,
            uploaded_results=uploaded_results,
            field="primary",
            comparisons=[
                ("Strict vs Baseline", "strict_primary"),
                ("Partial vs Baseline", "partial_primary"),
                ("Lax vs Baseline", "none_primary"),
            ],
        )

        f.write("\n#### Inline Codelists\n\n")
        write_uploaded_scenario_table(f, inline_results, "primary")
        write_unaffected_table(
            f,
            inline_results,
            builder_results=None,
            uploaded_results=inline_results,
            field="primary",
            comparisons=[
                ("Strict vs Baseline", "strict_primary"),
                ("Partial vs Baseline", "partial_primary"),
            ],
        )

        # Secondary counts analysis
        f.write("\n## Secondary Diagnosis Field\n\n")
        f.write(
            "This field is exactly the same as the primary diagnosis field so we just repeat the above analysis here.\n\n"
        )
        write_scenario_table(f, results, "secondary")

        f.write("### Unaffected Codelists\n\n")
        write_unaffected_table(
            f,
            results,
            builder_results,
            uploaded_results,
            field="secondary",
            comparisons=[
                ("Strict vs Baseline", "strict_secondary"),
                ("Partial vs Baseline", "partial_secondary"),
            ],
        )

        f.write("\n### By Creation Method\n\n")
        f.write("#### Builder Codelists\n\n")
        write_scenario_table(f, builder_results, "secondary")

        f.write("\n#### Uploaded Codelists\n\n")
        write_uploaded_scenario_table(f, uploaded_results, "secondary")
        write_unaffected_table(
            f,
            uploaded_results,
            builder_results=None,
            uploaded_results=uploaded_results,
            field="secondary",
            comparisons=[
                ("Strict vs Baseline", "strict_secondary"),
                ("Partial vs Baseline", "partial_secondary"),
                ("Lax vs Baseline", "none_secondary"),
            ],
        )

        f.write("\n#### Inline Codelists\n\n")
        write_uploaded_scenario_table(f, inline_results, "secondary")
        write_unaffected_table(
            f,
            inline_results,
            builder_results=None,
            uploaded_results=inline_results,
            field="secondary",
            comparisons=[
                ("Strict vs Baseline", "strict_secondary"),
                ("Partial vs Baseline", "partial_secondary"),
            ],
        )

        # All counts analysis
        f.write("\n## All Diagnosis Field\n\n")
        f.write(
            "This field contains all ICD10 codes recorded during a patient spell "
            "in hospital. It contains a concatenated list of ICD10 codes. The codes "
            "are usually in the same format as those in the primary and secondary "
            "diagnosis fields (i.e., 4 or 5 characters, with 3 character codes padded "
            "with an X). However, the field doesn't seem to have as much validation "
            "and so you do get exceptions e.g. 3 character codes without the X padding. "
            "However, these are always below the 15 usage threshold so we ignore them in this analysis.\n\n"
            "Currently, the way we query this field with ehrQL, means that prefix matching "
            "is ALWAYS applied. This means that if you have a codelist with `PARTIAL` codes, "
            "that is places where a parent code is included, and some, but not all, of its "
            "children are deliberatly excluded suggesting the intention is for only the "
            "included codes to be matched, so the prefix matching would lead to inadvertent inclusion "
            "of those excluded children.\n\n"
            "For our analysis we report:\n"
            "|Strategy|Description|\n"
            "|----|----|\n"
            "|Baseline| Total event count in this field using just codes in the codelist|\n"
            "|With PARTIAL descendants| Total event count when including codes that are children of `PARTIAL` codes|\n\n"
        )
        write_all_table(f, results)

        f.write("### Unaffected Codelists\n\n")
        write_unaffected_table(
            f,
            results,
            builder_results,
            uploaded_results,
            field="all",
            comparisons=[
                ("PARTIAL descendants vs Baseline", "with_partial_children_all"),
            ],
        )

        f.write("\n### By Creation Method\n\n")
        f.write("#### Builder Codelists\n\n")
        write_all_table(f, builder_results)

        f.write("\n#### Uploaded Codelists\n\n")
        write_all_table(f, uploaded_results)


def write_scenario_table(f, results, field):
    """Write a table comparing baseline, strict, and partial scenarios."""
    baseline_key = f"baseline_{field}"
    strict_key = f"strict_{field}"
    partial_key = f"partial_{field}"

    total_baseline = sum(r[baseline_key] for r in results)
    total_strict = sum(r[strict_key] for r in results)
    total_partial = sum(r[partial_key] for r in results)

    strict_diff = total_strict - total_baseline
    partial_diff = total_partial - total_baseline

    strict_pct = (strict_diff / total_baseline * 100) if total_baseline > 0 else 0
    partial_pct = (partial_diff / total_baseline * 100) if total_baseline > 0 else 0

    f.write("| Scenario | Total Events | Difference from Baseline | % Increase |\n")
    f.write("|----------|-------------:|-------------------------:|-----------:|\n")
    f.write(f"| Baseline | {total_baseline:,} | - | - |\n")
    f.write(f"| Strict | {total_strict:,} | +{strict_diff:,} | +{strict_pct:.2f}% |\n")
    f.write(
        f"| Partial | {total_partial:,} | +{partial_diff:,} | +{partial_pct:.2f}% |\n"
    )
    f.write("\n")


def write_uploaded_scenario_table(f, results, field):
    """Write a table comparing baseline, strict, partial, and lax scenarios for uploaded codelists."""
    baseline_key = f"baseline_{field}"
    strict_key = f"strict_{field}"
    partial_key = f"partial_{field}"
    none_key = f"none_{field}"

    total_baseline = sum(r[baseline_key] for r in results)
    total_strict = sum(r[strict_key] for r in results)
    total_partial = sum(r[partial_key] for r in results)
    total_none = sum(r[none_key] for r in results)
    total_lax = total_baseline + total_none

    strict_diff = total_strict - total_baseline
    partial_diff = total_partial - total_baseline
    lax_diff = total_lax - total_baseline

    strict_pct = (strict_diff / total_baseline * 100) if total_baseline > 0 else 0
    partial_pct = (partial_diff / total_baseline * 100) if total_baseline > 0 else 0
    lax_pct = (lax_diff / total_baseline * 100) if total_baseline > 0 else 0

    f.write("| Scenario | Total Events | Difference from Baseline | % Increase |\n")
    f.write("|----------|-------------:|-------------------------:|-----------:|\n")
    f.write(f"| Baseline | {total_baseline:,} | - | - |\n")
    f.write(f"| Strict | {total_strict:,} | +{strict_diff:,} | +{strict_pct:.2f}% |\n")
    f.write(
        f"| Partial | {total_partial:,} | +{partial_diff:,} | +{partial_pct:.2f}% |\n"
    )
    f.write(f"| Lax | {total_lax:,} | +{lax_diff:,} | +{lax_pct:.2f}% |\n")
    f.write("\n")


def write_none_table(f, results, field):
    """Write a table showing impact of including NONE descendants."""
    baseline_key = f"baseline_{field}"
    none_key = f"none_{field}"

    total_baseline = sum(r[baseline_key] for r in results)
    total_none_extra = sum(r[none_key] for r in results)
    total_with_none = total_baseline + total_none_extra

    none_pct = (total_none_extra / total_baseline * 100) if total_baseline > 0 else 0

    f.write("| Scenario | Total Events | Additional Events | % Increase |\n")
    f.write("|----------|-------------:|------------------:|-----------:|\n")
    f.write(f"| Baseline | {total_baseline:,} | - | - |\n")
    f.write(
        f"| Lax | {total_with_none:,} | +{total_none_extra:,} | +{none_pct:.2f}% |\n"
    )
    f.write("\n")


def write_all_table(f, results):
    """Write a table showing impact of PARTIAL prefix matching."""
    total_baseline = sum(r["baseline_all"] for r in results)
    total_with_partial = sum(r["with_partial_children_all"] for r in results)

    diff = total_with_partial - total_baseline
    pct = (diff / total_baseline * 100) if total_baseline > 0 else 0

    f.write("| Scenario | Total Events | Inadvertent Inclusion | % Increase |\n")
    f.write("|----------|-------------:|----------------------:|-----------:|\n")
    f.write(f"| Baseline (codelist codes only) | {total_baseline:,} | - | - |\n")
    f.write(
        f"| With PARTIAL descendants (prefix matching) | {total_with_partial:,} | +{diff:,} | +{pct:.2f}% |\n"
    )
    f.write("\n")


def write_unaffected_table(
    f,
    all_results,
    builder_results,
    uploaded_results,
    *,
    field,
    comparisons,
):
    """Write a table showing codelists unaffected by each scenario."""

    def unaffected_counts(dataset, baseline_key, scenario_key):
        total = len(dataset)
        unaffected = sum(1 for r in dataset if r[baseline_key] == r[scenario_key])
        pct = (unaffected / total * 100) if total > 0 else 0
        return total, unaffected, pct

    def fmt(total, unaffected, pct):
        if total == 0:
            return "-"
        return f"{unaffected}/{total} ({pct:.1f}%)"

    baseline_key = "baseline_all" if field == "all" else f"baseline_{field}"

    f.write("| Comparison | All Codelists | Builder | Uploaded |\n")
    f.write("|------------|--------------|---------|----------|\n")

    for label, scenario_key in comparisons:
        all_total, all_unaff, all_pct = unaffected_counts(
            all_results, baseline_key, scenario_key
        )
        row = [label, fmt(all_total, all_unaff, all_pct)]

        if builder_results is not None:
            b_total, b_unaff, b_pct = unaffected_counts(
                builder_results, baseline_key, scenario_key
            )
            row.append(fmt(b_total, b_unaff, b_pct))
        else:
            row.append("-")

        if uploaded_results is not None:
            u_total, u_unaff, u_pct = unaffected_counts(
                uploaded_results, baseline_key, scenario_key
            )
            row.append(fmt(u_total, u_unaff, u_pct))
        else:
            row.append("-")

        f.write("| " + " | ".join(row) + " |\n")

    f.write("\n")


# ============================================================================
# Stage 2: Repo Mapping Functions
# ============================================================================


def load_prefix_matching_results():
    """Load the prefix matching analysis results and find codelists with discrepancies."""
    discrepancies = []

    with open(OUTPUT_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            codelist_id = row["codelist_id"]
            baseline_primary = int(row.get("baseline_primary", 0))
            strict_primary = int(row.get("strict_primary", 0))
            none_primary = int(row.get("none_primary", 0))

            # Check if there's a discrepancy
            if strict_primary != baseline_primary or none_primary > 0:
                # Take max of strict_primary and none_primary
                with_prefix_matching = max(strict_primary, none_primary)

                # Calculate percentage increase from baseline to with_prefix_matching
                if baseline_primary > 0:
                    pct_diff = (
                        (with_prefix_matching - baseline_primary) / baseline_primary
                    ) * 100
                else:
                    # Mark as "Infinite" when baseline is 0
                    pct_diff = None

                discrepancies.append(
                    {
                        "codelist_id": codelist_id,
                        "baseline_primary": baseline_primary,
                        "with_prefix_matching": with_prefix_matching,
                        "pct_difference": pct_diff,
                    }
                )

    return discrepancies


def load_ehrql_codelists_to_repos():
    """Load ehrql_codelists.json and map codelists to repos that use them.

    Returns:
        Dict of {codelist_id: set(repos)}
    """
    with open(EHRQL_JSON_FILE) as f:
        data = json.load(f)

    # First, build a mapping of file_hash -> set of repos that use it
    # projects[repo][commit] = file_hash
    file_hash_to_repos = defaultdict(set)
    projects = data.get("projects", {})
    for repo_name, commit_dict in projects.items():
        if isinstance(commit_dict, dict):
            for commit_hash, file_hash in commit_dict.items():
                file_hash_to_repos[file_hash].add(repo_name)

    # Build mapping: codelist_id -> set of repos
    codelist_to_repos = defaultdict(set)

    # Navigate signatures structure: hash -> filename -> variable -> codelist_list
    signatures = data.get("signatures", {})
    for file_hash, files in signatures.items():
        # Get repos that use this file hash
        repos_for_hash = file_hash_to_repos.get(file_hash, set())

        for filename, variables in files.items():
            for variable_name, codelist_list in variables.items():
                # codelist_list is a list of entries, each starting with codelist_id
                for entry in codelist_list:
                    if entry and len(entry) > 0:
                        codelist_id = entry[0]
                        if codelist_id and codelist_id != "<inline>":
                            # Add all repos that use this file hash
                            codelist_to_repos[codelist_id].update(repos_for_hash)

    return codelist_to_repos


def map_to_repos():
    """Map codelists with discrepancies to GitHub repos."""
    print("\nLoading prefix matching discrepancies...")
    discrepancies = load_prefix_matching_results()
    print(f"  Found {len(discrepancies)} codelists with discrepancies")

    print("Loading ehrql codelists and repo mappings...")
    codelist_to_repos = load_ehrql_codelists_to_repos()
    print(f"  Mapped {len(codelist_to_repos)} codelists to repos")

    # Build output rows
    output_rows = []
    for disc in discrepancies:
        codelist_id = disc["codelist_id"]
        repos = codelist_to_repos.get(codelist_id, set())

        # Format percentage increase
        if disc["pct_difference"] is None:
            pct_str = "Infinite"
        else:
            pct_str = f"{round(disc['pct_difference'])}%"

        if repos:
            for repo in sorted(repos):
                output_rows.append(
                    {
                        "repo": repo,
                        "codelist": codelist_id,
                        "current_event_count": disc["baseline_primary"],
                        "event_count_with_prefix_matching": disc[
                            "with_prefix_matching"
                        ],
                        "percentage_increase": pct_str,
                    }
                )
        else:
            # Include codelists that weren't found in any repo (for reference)
            output_rows.append(
                {
                    "repo": "(not found in repos)",
                    "codelist": codelist_id,
                    "current_event_count": disc["baseline_primary"],
                    "event_count_with_prefix_matching": disc["with_prefix_matching"],
                    "percentage_increase": pct_str,
                }
            )

    # Sort by repo, then codelist
    output_rows.sort(key=lambda x: (x["repo"], x["codelist"]))

    # Write CSV
    print(f"Writing repo mapping to {REPOS_OUTPUT_FILE}...")
    with open(REPOS_OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "repo",
                "codelist",
                "current_event_count",
                "event_count_with_prefix_matching",
                "percentage_increase",
            ],
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nWrote {len(output_rows)} rows to {REPOS_OUTPUT_FILE}")
    print(
        f"Summary: {len(discrepancies)} codelists with discrepancies "
        f"across {len(set(r['repo'] for r in output_rows))} repos"
    )


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    run_analysis()
    print("\n" + "=" * 80)
    map_to_repos()

    return 0


if __name__ == "__main__":
    exit(main())
