#!/usr/bin/env python3
"""
Analyze codelist coverage against actual ICD-10 code usage.

For each codelist:
1. Identify which codes have ALL/NONE/SOME descendants in the codelist
2. Calculate total usage from code_usage_combined_apcs.csv and code_usage_combined_ons_deaths.csv
3. Identify missing descendant codes that would increase coverage

Generates separate reports for APCS and ONS deaths data.
"""

import csv
import sys
from collections import defaultdict

from .common import (
    CACHE_DIR,
    find_code_column,
    get_output_file,
    load_all_icd10_codelists_from_rsi,
    load_codelist,
    load_icd10_codelists,
    load_ocl_codes,
    load_rsi_codelists,
    load_usage_data,
)


def get_descendants(code, all_codes):
    """Get all descendant codes of a given code from the set of all codes.

    ICD-10 is a prefix hierarchy: E1112 is a child of E111 is a child of E11.
    """
    descendants = set()
    for candidate in all_codes:
        # A code is a descendant if it starts with the parent code and is longer
        if candidate != code and candidate.startswith(code):
            descendants.add(candidate)
    return descendants


def classify_code_descendants(code, codelist_codes, hierarchy_ocl_codes):
    """Classify a code based on its descendants in the codelist.

    Rules:
    - If 4 characters or all descendants in codelist (or no descendants): return "COMPLETE"
    - If some descendants in codelist: return "PARTIAL"
    - If no descendants from OCL are in codelist (but some exist in OCL): return "NONE"

    Args:
        code: The code to classify
        codelist_codes: Set of codes in the codelist
        hierarchy_ocl_codes: Set of OCL codes to use for hierarchy
            Use the ONS deaths OCL codes here to get the true ICD-10 hierarchy,
            not the APCS codes which include synthetic X-suffixed codes.

    Returns: "COMPLETE", "PARTIAL", "NONE"
    """

    # Rule 1: If exactly 4 characters, return COMPLETE (OCL at the time of writing didn't have 5 character codes)
    if len(code) == 4:
        return "COMPLETE"

    # Get all possible descendants from hierarchy OCL codes
    ocl_descendants = get_descendants(code, hierarchy_ocl_codes)

    # No descendants means COMPLETE (it's a leaf)
    if not ocl_descendants:
        return "COMPLETE"

    # Check how many of the possible descendants are in the codelist
    descendants_in_codelist = ocl_descendants & codelist_codes

    if len(descendants_in_codelist) == len(ocl_descendants):
        return "COMPLETE"
    elif len(descendants_in_codelist) == 0:
        return "NONE"
    else:
        return "PARTIAL"


def analyze_codelist(
    codelist_id,
    codelist_codes,
    ocl_codes,
    usage_codes,
    usage_data,
    creation_method,
    hierarchy_ocl_codes,
    from_ehrql=False,
):
    """Analyze a single codelist for coverage."""

    # Classify each code in the codelist as COMPLETE/PARTIAL/NONE
    code_classifications = {}
    for code in codelist_codes:
        if code in hierarchy_ocl_codes:
            classification = classify_code_descendants(
                code, codelist_codes, hierarchy_ocl_codes
            )
            code_classifications[code] = classification

    # Calculate actual usage of codes in the codelist
    actual_usage = defaultdict(int)
    for code in codelist_codes:
        if code in usage_data:
            for key, count in usage_data[code].items():
                actual_usage[key] += count

    # Find missing descendants in usage data
    missing_descendants = set()
    for code in codelist_codes:
        # Get all descendants from OCL
        ocl_descendants = get_descendants(code, ocl_codes)
        # Get all descendants from usage data
        usage_descendants = set()
        for usage_code in usage_codes:
            if usage_code != code and usage_code.startswith(code):
                usage_descendants.add(usage_code)

        # Missing = in usage but not in OCL
        missing = usage_descendants - ocl_descendants
        missing_descendants.update(missing)

    # Calculate potential additional usage from missing descendants
    potential_usage = defaultdict(int)
    for code in missing_descendants:
        if code in usage_data:
            for key, count in usage_data[code].items():
                potential_usage[key] += count

    return {
        "codelist_id": codelist_id,
        "creation_method": creation_method,
        "from_ehrql": from_ehrql,
        "total_codes": len(codelist_codes),
        "codelist_codes": codelist_codes,  # Store the actual codes for CSV output
        "code_classifications": code_classifications,
        "actual_usage": dict(actual_usage),
        "missing_descendants": sorted(missing_descendants),
        "potential_usage": dict(potential_usage),
    }


def format_number(n):
    """Format number with thousands separator."""
    return f"{n:,}"


def write_csv_report(
    results,
    usage_data,
    raw_usage,
    output_file,
    data_source,
    hierarchy_ocl_codes,
):
    """Write detailed CSV report with code-level breakdown using raw values.

    Args:
        data_source: Either 'apcs' or 'ons_deaths' - used for filtering usage columns
        hierarchy_ocl_codes: OCL codes to use for hierarchy classification
    """

    # Get all 2024-25 category columns from usage data for this data source
    usage_columns = []
    if usage_data:
        # Filter columns based on data source
        prefix = "apcs_" if data_source == "apcs" else "ons_"
        # Collect all unique category columns with 2024-25 data
        for code in usage_data:
            for category, year in usage_data[code].keys():
                if (
                    year == "2024-25"
                    and category.startswith(prefix)
                    and category not in usage_columns
                ):
                    usage_columns.append(category)
    usage_columns = sorted(usage_columns)

    # Sort results: EHRQL codelists first (from_ehrql=True), then others
    results.sort(key=lambda r: (not r.get("from_ehrql", False), r["codelist_id"]))

    with open(output_file, "w", newline="") as f:
        fieldnames = [
            "codelist_id",
            "creation_method",
            "Exists in ehrQL repo",
            "icd10_code",
            "status",
        ] + usage_columns
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            codelist_id = result["codelist_id"]
            creation_method = result.get("creation_method", "")
            from_ehrql_flag = "Y" if result.get("from_ehrql", False) else "N"
            # Use codelist_codes from result if available, otherwise try to reload
            if "codelist_codes" in result:
                codelist_codes = result["codelist_codes"]
            else:
                codelist_codes = set()
                # Reload codelist to get the actual codes
                cache_filename = codelist_id.strip("/").replace("/", "_") + ".csv"
                cache_path = CACHE_DIR / cache_filename
                if cache_path.exists():
                    with open(cache_path, encoding="utf-8") as cf:
                        reader = csv.DictReader(cf)
                        code_col = find_code_column(reader.fieldnames)
                        if code_col:
                            for row in reader:
                                code = row.get(code_col, "").strip()
                                if code:
                                    codelist_codes.add(code)

            # Collect all rows for this codelist before writing
            rows_to_write = []
            written_codes = set()

            # Get code classifications from result
            code_classifications = result.get("code_classifications", {})

            # First pass: collect codes that are in the codelist
            for code in codelist_codes:
                # Get status from pre-computed classifications
                status = code_classifications.get(code)
                if status is None:
                    # Fallback to calculating
                    status = classify_code_descendants(
                        code, codelist_codes, hierarchy_ocl_codes
                    )

                # Get usage data for this code for 2024-25 (using raw values)
                row_data = {
                    "codelist_id": codelist_id,
                    "creation_method": creation_method,
                    "Exists in ehrQL repo": from_ehrql_flag,
                    "icd10_code": code,
                    "status": status,
                }
                for col in usage_columns:
                    raw_value = raw_usage.get(code, {}).get((col, "2024-25"), "")
                    row_data[col] = raw_value if raw_value else ""

                rows_to_write.append(row_data)
                written_codes.add(code)

            # Second pass: collect EXTRA codes from usage data that are descendants
            # of COMPLETE/PARTIAL codes, or NONE codes for uploaded codelists
            for usage_code in usage_data.keys():
                if usage_code not in written_codes:
                    # Check if this usage code is a descendant of any codelist code
                    for parent_code, status in code_classifications.items():
                        # Include descendants of COMPLETE and PARTIAL codes
                        # For uploaded codelists, also include descendants of NONE codes
                        should_include = status in ("COMPLETE", "PARTIAL") or (
                            creation_method == "Uploaded" and status == "NONE"
                        )

                        if (
                            should_include
                            and usage_code.startswith(parent_code)
                            and usage_code != parent_code
                        ):
                            # This is an extra descendant
                            row_data = {
                                "codelist_id": codelist_id,
                                "creation_method": creation_method,
                                "Exists in ehrQL repo": from_ehrql_flag,
                                "icd10_code": usage_code,
                                "status": "EXTRA",
                            }
                            for col in usage_columns:
                                raw_value = raw_usage.get(usage_code, {}).get(
                                    (col, "2024-25"), ""
                                )
                                row_data[col] = raw_value if raw_value else ""

                            rows_to_write.append(row_data)
                            written_codes.add(usage_code)
                            break  # Don't add the same code multiple times

            # Sort all rows by icd10_code and write them
            for row_data in sorted(rows_to_write, key=lambda r: r["icd10_code"]):
                writer.writerow(row_data)


def analyze_data_source(
    data_source, ocl_codes, icd10_codelists, inline_codelists, rsi_map, ehrql_set
):
    """Analyze coverage for a specific data source (APCS or ONS deaths)."""
    source_label = "APCS" if data_source == "apcs" else "ONS Deaths"

    print(f"\n{'=' * 80}", file=sys.stderr)
    print(f"Analyzing {source_label}", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    print(f"\nLoading {source_label} usage data...", file=sys.stderr)
    usage_data, raw_usage = load_usage_data(data_source)
    usage_codes = set(usage_data.keys())
    print(f"  Loaded usage for {len(usage_codes)} codes", file=sys.stderr)

    # Get the OCL codes for this data source
    source_ocl_codes = ocl_codes[data_source]
    # Always use ONS deaths codes for hierarchy (true ICD-10 structure)
    hierarchy_ocl_codes = ocl_codes["ons_deaths"]
    print(
        f"  Using {len(source_ocl_codes)} OCL codes for {source_label}", file=sys.stderr
    )

    print(f"\nAnalyzing codelists for {source_label}...", file=sys.stderr)

    results = []

    # Analyze named codelists
    for i, codelist_id in enumerate(icd10_codelists, 1):
        print(f"[{i}/{len(icd10_codelists)}] {codelist_id}", file=sys.stderr)

        codelist_codes = load_codelist(codelist_id)
        if codelist_codes is None:
            continue

        # Get creation_method from metadata
        creation_method = None
        if codelist_id in rsi_map:
            creation_method = rsi_map[codelist_id]["creation_method"]
        else:
            # Try hash-only match
            parts = codelist_id.strip("/").split("/")
            if parts:
                last_part = parts[-1]
                if last_part in rsi_map:
                    creation_method = rsi_map[last_part]["creation_method"]

        from_ehrql = codelist_id in ehrql_set

        result = analyze_codelist(
            codelist_id,
            codelist_codes,
            source_ocl_codes,
            usage_codes,
            usage_data,
            creation_method,
            hierarchy_ocl_codes,
            from_ehrql,
        )
        results.append(result)

    # Analyze inline codelists
    for i, inline_cl in enumerate(inline_codelists, 1):
        inline_id = inline_cl["id"]
        inline_codes = inline_cl["codes"]
        print(
            f"[{len(icd10_codelists) + i}/{len(icd10_codelists) + len(inline_codelists)}] {inline_id}",
            file=sys.stderr,
        )

        result = analyze_codelist(
            inline_id,
            inline_codes,
            source_ocl_codes,
            usage_codes,
            usage_data,
            creation_method="Inline",
            hierarchy_ocl_codes=hierarchy_ocl_codes,
            from_ehrql=True,
        )
        results.append(result)

    # Write CSV report
    csv_file = get_output_file(data_source)
    print(f"Writing CSV detail to {csv_file}...", file=sys.stderr)
    write_csv_report(
        results,
        usage_data,
        raw_usage,
        csv_file,
        data_source,
        hierarchy_ocl_codes,
    )


def main():
    print("Loading OCL ICD-10 codes...", file=sys.stderr)
    ocl_codes = load_ocl_codes()
    print(
        f"  Loaded {len(ocl_codes['ons_deaths'])} codes from OpenCodelists (ONS deaths)",
        file=sys.stderr,
    )
    print(f"  Generated {len(ocl_codes['apcs'])} codes for APCS", file=sys.stderr)

    # Load RSI metadata to get creation_method
    print("\nLoading codelist metadata...", file=sys.stderr)
    rsi_map = load_rsi_codelists()

    print("\nLoading ICD-10 codelists from EHRQL...", file=sys.stderr)
    icd10_codelists, inline_codelists = load_icd10_codelists(rsi_map)
    print(f"  Found {len(icd10_codelists)} named ICD-10 codelists", file=sys.stderr)
    print(
        f"  Found {len(inline_codelists)} unique inline ICD-10 codelists",
        file=sys.stderr,
    )

    ehrql_set = set(icd10_codelists)

    # Load ALL ICD-10 codelists from RSI (includes 881 user codelists)
    print(
        "\nLoading ALL ICD-10 codelist versions from RSI data...",
        file=sys.stderr,
    )
    all_icd10_versions = load_all_icd10_codelists_from_rsi()

    # Combine: EHRQL codelists + all RSI versions (deduplicated)
    combined_codelists = list(set(icd10_codelists + all_icd10_versions))
    print(
        f"  Total unique ICD-10 codelist versions to analyze: {len(combined_codelists)}",
        file=sys.stderr,
    )

    # Analyze APCS
    analyze_data_source(
        "apcs",
        ocl_codes,
        combined_codelists,
        inline_codelists,
        rsi_map,
        ehrql_set,
    )

    # Analyze ONS Deaths
    analyze_data_source(
        "ons_deaths",
        ocl_codes,
        combined_codelists,
        inline_codelists,
        rsi_map,
        ehrql_set,
    )


if __name__ == "__main__":
    main()
