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
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .common import load_ocl_codes


# Paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "reporting" / "data"
OUTPUT_DIR = REPO_ROOT / "reporting" / "outputs"
CACHE_DIR = DATA_DIR / "codelist_cache"
OCL_CODES_FILE = DATA_DIR / "ocl_icd10_codes.txt"
USAGE_FILE_APCS = OUTPUT_DIR / "code_usage_combined_apcs.csv"
USAGE_FILE_ONS_DEATHS = OUTPUT_DIR / "code_usage_combined_ons_deaths.csv"
EHRQL_JSON_FILE = DATA_DIR / "ehrql_codelists.json"
RSI_JSON_FILE = DATA_DIR / "rsi-codelists-analysis.json"


def load_rsi_codelists():
    """
    Load all the codelists from OpenCodelists (from the RSI export from previous work).
    Returns a mapping of version slugs and hashes to coding system and creation method.
    """
    with open(RSI_JSON_FILE) as f:
        data = json.load(f)

    # Build a mapping: version_slug or hash-> (coding_system, full_entry)
    # Each codelist can have multiple versions
    codelist_map = {}

    for entry in data:
        coding_system = entry.get("coding_system", "")
        base_slug = entry.get("slug", "")
        versions = entry.get("versions", [])

        for version in versions:
            tag = version.get("tag")
            hash_val = version.get("hash")

            metadata = {
                "coding_system": coding_system,
                "creation_method": version.get("creation_method", ""),
            }

            # Create entries for both tag and hash based slugs
            if tag:
                tag_slug = f"/{base_slug}/{tag}/"
                codelist_map[tag_slug] = metadata

            if hash_val:
                assert hash_val not in codelist_map, f"Duplicate hash {hash_val}"
                codelist_map[hash_val] = metadata

    return codelist_map


def extract_codelist_ids(json_path):
    """Extract all unique codelist IDs from the signatures structure.

    Returns:
        Tuple of (codelist_ids, inline_codelists) where inline_codelists is a list of
        tuples (sorted_codes,) that uniquely identify each inline codelist.
    """
    with open(json_path) as f:
        data = json.load(f)

    codelist_ids = set()
    inline_codelists = set()

    # Navigate: signatures > hash > filename > variable_name > list of lists
    signatures = data.get("signatures", {})
    for hash_value, files in signatures.items():
        for filename, variables in files.items():
            for variable_name, codelist_list in variables.items():
                # codelist_list is a list of entries, each entry is [codelist_id, ...]
                for entry in codelist_list:
                    if entry and len(entry) > 0:
                        # First element of each entry is the codelist ID
                        codelist_id = entry[0]
                        if codelist_id:
                            if codelist_id == "<inline>":
                                # For inline, extract codes from 4th element (index 3)
                                # Should be "values={pipe separated list}"
                                values_str = entry[3]
                                codes = values_str[7:]  # Remove "values=" prefix
                                # Split by pipe, sort, and create normalized representation
                                code_list = [c.strip() for c in codes.split("|")]
                                # Use sorted tuple as hashable unique identifier
                                normalized = tuple(sorted(code_list))
                                inline_codelists.add(normalized)
                            else:
                                codelist_ids.add(codelist_id)

    return sorted(codelist_ids), sorted(inline_codelists)


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


def load_usage_data(data_source):
    """Load code usage data from CSV for a specific data source.

    Args:
        data_source: Either 'apcs' or 'ons_deaths'

    Returns: tuple of (usage, raw_usage)
    - usage: dict of {code: {(category, year): count}} with processed values
    - raw_usage: dict of {code: {(category, year): raw_value}} with original string values
    where category is like 'apcs_primary_count', 'ons_contributing_count', etc.
    """
    usage_file = USAGE_FILE_APCS if data_source == "apcs" else USAGE_FILE_ONS_DEATHS
    usage = defaultdict(lambda: defaultdict(int))
    raw_usage = defaultdict(lambda: defaultdict(str))

    with open(usage_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["icd10_code"]
            year = row["financial_year"]

            # Process each count column
            for col in reader.fieldnames:
                if col not in ["icd10_code", "financial_year", "in_opencodelists"]:
                    value = row[col]
                    raw_usage[code][(col, year)] = value  # Store original value

                    # Treat suppressed values like '<15' as 0
                    if value.startswith("<"):
                        count = 0
                    else:
                        count = int(value) if value else 0

                    usage[code][(col, year)] += count

    return usage, raw_usage


def find_code_column(fieldnames):
    """Find the column name that contains the codes."""
    for candidate in ["code", "icd10_code", "icd", "ICD_code"]:
        if candidate in fieldnames:
            return candidate

    # Try case-insensitive
    lower_fields = {name.lower(): name for name in fieldnames}
    for candidate in ["code", "icd10_code", "icd", "icd_code"]:
        if candidate in lower_fields:
            return lower_fields[candidate]

    return None


def parse_codelist(filename):
    cache_path = CACHE_DIR / filename
    codes = set()
    try:
        with open(cache_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            code_col = find_code_column(reader.fieldnames)
            if code_col is None:
                return None

            for row in reader:
                code = row.get(code_col, "").strip()
                if code:
                    codes.add(code)
    except Exception as e:
        print(f"Error loading {filename}: {e}", file=sys.stderr)
        return None
    return codes


def download_codelist(codelist_id):
    """
    Download a codelist from OpenCodelists and return the list of codes.

    Args:
        codelist_id: The codelist ID (e.g., "/opensafely/asthma/2024-05-01/")

    Returns:
        List of codes from the "code" column, or None if download failed
    """
    # Create cache filename from codelist_id (replace slashes with underscores)
    cache_filename = codelist_id.strip("/").replace("/", "_") + ".csv"
    cache_path = CACHE_DIR / cache_filename

    # Download from OpenCodelists
    url = f"https://www.opencodelists.org/codelist{codelist_id}download.csv"

    try:
        # Create request with a user agent to be polite
        request = Request(url, headers={"User-Agent": "opensafely/tpp-code-counts/1.0"})

        with urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8")

            # Save to cache
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(content)
    except HTTPError as e:
        print(f"  WARNING: HTTP {e.code} for {codelist_id}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"  WARNING: URL error for {codelist_id}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  WARNING: Error downloading {codelist_id}: {e}", file=sys.stderr)
        return None


def load_codelist(codelist_id):
    """Load codes from a cached codelist CSV - or from download if not exists

    Args:
        codelist_id: The codelist ID (string)
        download: Force re-download
        inline_codes: If provided and codelist_id starts with '<inline>', use these codes

    Returns:
        Set of codes, or None if loading failed
    """

    cache_filename = codelist_id.strip("/").replace("/", "_") + ".csv"
    cache_path = CACHE_DIR / cache_filename

    # if cached file not exists OR if download is True
    if not cache_path.exists():
        # Download and cache the codelist
        download_codelist(codelist_id)

    return parse_codelist(cache_filename)


def is_icd10_code(code):
    """Check if a code matches ICD-10 format.

    ICD-10 format: Capital letter, followed by 2-4 digits, optionally with 'X' as 4th character.
    Examples: E10, E110, E1101, E10X, M907, S92X, S92X0
    """
    # Pattern: Capital letter, then 2-4 characters that are digits or X
    # But X should only appear as the 4th character (position 3)
    pattern = r"^[A-Z]\d{2}[0-9X]?[0-9]?$"
    return bool(re.match(pattern, code))


def load_icd10_codelists(rsi_map):
    """Load the list of ICD-10 codelist IDs from the ehrql extraction logic.

    Returns:
        Tuple of (codelist_ids, inline_codelists) where inline_codelists are dicts with
        'id' (synthetic ID) and 'codes' (set of codes).
    """
    # Extract codelist IDs from ehrql file
    codelist_ids, inline_tuples = extract_codelist_ids(EHRQL_JSON_FILE)

    # Filter named codelists for ICD-10 only
    icd10_codelists = []
    for codelist_id in codelist_ids:
        if codelist_id in rsi_map:
            coding_system = rsi_map[codelist_id]["coding_system"].lower()
            if coding_system == "icd10":
                icd10_codelists.append(codelist_id)
        else:
            # Try hash-only match
            parts = codelist_id.strip("/").split("/")
            if parts:
                last_part = parts[-1]
                if last_part in rsi_map:
                    coding_system = rsi_map[last_part]["coding_system"].lower()
                    if coding_system == "icd10":
                        icd10_codelists.append(codelist_id)
                else:
                    print(
                        f"  WARNING: Codelist {codelist_id} not found in RSI metadata",
                        file=sys.stderr,
                    )

    # Process inline codelists - filter for ICD-10 codes only
    inline_codelists = []
    for code_tuple in inline_tuples:
        # Check if all codes match ICD-10 format
        if all(is_icd10_code(code) for code in code_tuple):
            # Create a synthetic ID for this inline codelist using a hash
            # This keeps the ID short and filesystem-friendly
            codes_str = "|".join(code_tuple)
            code_hash = hashlib.md5(codes_str.encode()).hexdigest()[:8]
            inline_id = f"<inline>:{code_hash}"
            inline_codelists.append(
                {
                    "id": inline_id,
                    "codes": set(code_tuple),
                    "codes_str": codes_str,  # Keep full description for reporting
                }
            )
        else:
            print(
                f"  WARNING: Inline codelist with non-ICD10 codes skipped: {code_tuple}",
                file=sys.stderr,
            )

    return sorted(icd10_codelists), inline_codelists


def load_all_icd10_codelists_from_rsi():
    """Load ALL ICD-10 codelist versions from the RSI export.

    This includes all public codelists (bristol, opensafely, ihme, etc.) AND
    881 user/* codelists that are not available in the OpenCodelists API.

    Returns:
        List of codelist_ids (full version slug format)
    """
    if not RSI_JSON_FILE.exists():
        print(
            f"  WARNING: RSI codelists file not found at {RSI_JSON_FILE}",
            file=sys.stderr,
        )
        return []

    try:
        with open(RSI_JSON_FILE) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"  WARNING: Could not load RSI codelists: {e}", file=sys.stderr)
        return []

    all_versions = []
    for item in data:
        if item.get("coding_system") == "icd10":
            for version in item.get("versions", []):
                version_slug = version.get("slug")
                if version_slug:
                    # Add leading and trailing slashes to match EHRQL format
                    # RSI has: user/name/hash -> we need: /user/name/hash/
                    normalized_slug = "/" + version_slug + "/"
                    all_versions.append(normalized_slug)

    print(
        f"  Found {len(all_versions)} ICD-10 codelist versions in RSI data",
        file=sys.stderr,
    )
    return all_versions


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
        if code in ocl_codes:
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

            # Track which codes we've already written
            written_codes = set()
            # Track code statuses for EXTRA row filtering
            code_statuses = {}

            # First pass: write codes that are in the codelist and record their statuses
            for code in sorted(codelist_codes):
                # Determine status based on OCL descendants
                status = classify_code_descendants(
                    code, codelist_codes, hierarchy_ocl_codes
                )
                code_statuses[code] = status

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

                writer.writerow(row_data)
                written_codes.add(code)

            # Second pass: add EXTRA codes from usage data that are descendants of non-NONE codes
            # For "Uploaded" codelists, also include descendants of NONE codes
            for usage_code in sorted(usage_data.keys()):
                if usage_code not in codelist_codes:
                    # Check if this usage code is a descendant of any codelist code
                    for parent_code, status in code_statuses.items():
                        should_include = False

                        # Include if descendant of non-NONE code
                        if status != "NONE":
                            should_include = True
                        # For uploaded codelists, also include descendants of NONE codes
                        elif creation_method == "Uploaded" and status == "NONE":
                            should_include = True

                        if (
                            should_include
                            and usage_code.startswith(parent_code)
                            and usage_code != parent_code
                        ):
                            if usage_code not in written_codes:
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

                                writer.writerow(row_data)
                                written_codes.add(usage_code)
                            break  # Don't add the same code multiple times


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

    suffix = "apcs" if data_source == "apcs" else "ons_deaths"

    # Write CSV report
    csv_file = (
        REPO_ROOT / "reporting" / "outputs" / f"codelist_coverage_detail_{suffix}.csv"
    )
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
