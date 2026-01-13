"""
File that looks at the codes available in the current version of ICD10 on OpenCodelists and
the outputs from the backend of what is used to report on:
- codes in OCL that are never used in practice
- codes used in practice that are missing from OCL
"""

import csv
import io
import re
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "reporting" / "data"
OUT_DIR = REPO_ROOT / "reporting" / "outputs"
OCL_ICD10_2019_CODES_FILE = DATA_DIR / "ocl_icd10_codes.txt"

# Precompiled regexes used by multiple functions
FILENAME_RE = re.compile(
    r"(?:output/)?icd10_(apcs|ons_deaths)_[0-9]{4}_[0-9]{2}.*\.csv"
)
FY_RE = re.compile(r"_(\d{4}_\d{2})")
# Regex to extract row numbers from filenames like "icd10_apcs_2016_17_rows_9983_14973.csv"
ROWS_RE = re.compile(r"_rows_(\d+)_(\d+)\.csv$")


def load_ocl_codes() -> set:
    """Load all ICD10 codes from OpenCodelists export.
    ONS death data is always 3 and 4 character ICD10 codes, while apcs
    pads 3 character codes without children with an X to make 4 character codes.
    """
    ocl_codes = {
        "apcs": set(),
        "ons_deaths": set(),
    }
    with open(OCL_ICD10_2019_CODES_FILE) as f:
        for line in f:
            code = line.strip()
            if code and "-" not in code:  # ocl contains code ranges which we'll ignore
                ocl_codes["ons_deaths"].add(code)
    # Should be at least 12,000
    assert len(ocl_codes["ons_deaths"]) >= 12000, "Loaded too few ICD10 codes from OCL"

    # Should contain some known codes
    for known_code in ["A00", "B99", "C341", "E119", "I10", "J459", "Z992"]:
        assert known_code in ocl_codes["ons_deaths"], (
            f"Known ICD10 code {known_code} missing from OCL codes"
        )

    # Now we create the APCS OCL codes set by adding 4-char codes with X suffixes
    for code in ocl_codes["ons_deaths"]:
        if len(code) != 3:
            ocl_codes["apcs"].add(code)
        else:
            # Check if this 3-char code has any children in OCL
            has_children = any(
                other_code.startswith(code) and len(other_code) > 3
                for other_code in ocl_codes["ons_deaths"]
            )
            if not has_children:
                # Add the 4-char code with X suffix
                ocl_codes["apcs"].add(f"{code}X")
    return ocl_codes


# In dev mode load the code usage from local files
LOCAL_USAGE_OUTPUT_DIR = REPO_ROOT / "output"
LOCAL_DATA_ZIP = DATA_DIR / "code_usage.zip"


def fy_from_filename(name: str) -> str:
    """Extract canonical financial-year string (e.g. '2024-25') from filename."""
    m = FY_RE.search(name)
    assert m, f"Could not extract financial year from filename: {name}"
    return m.group(1).replace("_", "-")


def get_file_key(name: str) -> str:
    """Get the key for deduplication - filename up to and including first row number.

    For example:
    - 'output/icd10_apcs_2016_17_rows_9983_13591.csv' -> 'output/icd10_apcs_2016_17_rows_9983'
    - 'output/icd10_apcs_2016_17_rows_9983_14973.csv' -> 'output/icd10_apcs_2016_17_rows_9983'
    - 'output/icd10_apcs_2021_22.csv' -> 'output/icd10_apcs_2021_22'
    """
    m = ROWS_RE.search(name)
    if m:
        # Return everything up to and including the first row number
        return name[: m.start()] + f"_rows_{m.group(1)}"
    # If no row numbers found, return up to .csv
    if name.endswith(".csv"):
        return name[:-4]
    return name


def deduplicate_files(names: list) -> list:
    """Keep only files with highest second row number when duplicates exist.

    If multiple files have the same prefix up to and including the first row number,
    only keep the one with the highest second row number.

    Also, if there are both chunked files (with _rows_) and non-chunked files for the
    same base name, skip the non-chunked file as it's likely incomplete.

    For example, given:
    - 'output/icd10_apcs_2016_17_rows_9983_13591.csv'
    - 'output/icd10_apcs_2016_17_rows_9983_14973.csv'

    Only keep the second one (14973 > 13591).

    And given:
    - 'output/icd10_apcs_2021_22.csv'
    - 'output/icd10_apcs_2021_22_rows_0001_4991.csv'

    Skip the first one (non-chunked version).
    """
    # First pass: identify base names that have chunked versions
    base_names_with_chunks = set()
    for name in names:
        m = ROWS_RE.search(name)
        if m:
            # Extract base name (everything before _rows_)
            base_name = name[: m.start()]
            base_names_with_chunks.add(base_name)

    # Second pass: group files by their deduplication key, excluding non-chunked if chunks exist
    by_key = defaultdict(list)
    for name in names:
        m = ROWS_RE.search(name)
        if not m:
            # Non-chunked file
            # Check if a chunked version exists
            if name.endswith(".csv"):
                base_name = name[:-4]
            else:
                base_name = name

            if base_name in base_names_with_chunks:
                # Skip this file - chunked versions exist
                continue

        key = get_file_key(name)
        by_key[key].append(name)

    # Third pass: for each group, pick the file with the highest second row number
    result = []
    for key, group in by_key.items():
        if len(group) == 1:
            result.append(group[0])
        else:
            # Multiple files with same prefix - pick the one with highest second row number
            best = None
            best_second_row = -1
            for name in group:
                m = ROWS_RE.search(name)
                if m:
                    second_row = int(m.group(2))
                    if second_row > best_second_row:
                        best_second_row = second_row
                        best = name
                else:
                    # Shouldn't happen given our filtering, but if no rows pattern, take first
                    if best is None:
                        best = name
            if best:
                result.append(best)

    return result


def process_csv(reader, name, usage):
    """Populate usage from a csv.DictReader and filename."""
    financial_year = fy_from_filename(name)
    is_apcs = "apcs" in name
    for row in reader:
        code = (row.get("icd10_code") or "").strip()
        u = usage["apcs" if is_apcs else "ons_deaths"][code][financial_year]
        if is_apcs:
            assert "apcs_primary_count" not in u, (
                f"Duplicate APCS counts for code {code} financial_year {financial_year} in file {name}"
            )
            u["apcs_primary_count"] = (row.get("primary_count") or "").strip()
            u["apcs_secondary_count"] = (row.get("secondary_count") or "").strip()
            u["apcs_all_count"] = (row.get("all_count") or "").strip()
        else:
            assert "ons_primary_count" not in u, (
                f"Duplicate ONS deaths counts for code {code} financial_year {financial_year} in file {name}"
            )
            primary = (row.get("primary_cause_count") or "").strip()
            contributing = (row.get("contributing_cause_count") or "").strip()
            u["ons_primary_count"] = primary
            u["ons_contributing_count"] = contributing


def load_code_usage_data():
    """Load all ICD10 codes and counts from the output files.

    Tries to load from (in order):
    1. Remote ZIP file from jobs.opensafely.org
    2. Local ZIP file in reporting/data/ folder
    3. Local CSV files in output/ folder (from running tests)

    Returns a mapping:
    {
      "apcs": {
        code -> { financial_year -> { counts } }
      },
      "ons_deaths": {
        code -> { financial_year -> { counts } }
      }
    }
    """
    usage = {
        "apcs": defaultdict(lambda: defaultdict(dict)),
        "ons_deaths": defaultdict(lambda: defaultdict(dict)),
    }

    csvs = None
    process_error = None

    # Strategy 1: Try to download zip from remote
    remote_url = "https://jobs.opensafely.org/opensafely-internal/tpp-code-counts/outputs/latest/download/"
    try:
        with urllib.request.urlopen(remote_url, timeout=20) as resp:
            data = resp.read()
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as z:
            names = [n for n in z.namelist() if n.endswith(".csv")]
        if names:
            csvs = (data, names)
        else:
            process_error = f"No CSV files found in remote zip from {remote_url}"
    except Exception as e:
        process_error = f"Could not download from {remote_url}: {str(e)}"

    # Strategy 2: If remote failed, try local ZIP in reporting/data/
    if not csvs and LOCAL_DATA_ZIP.exists():
        try:
            with open(LOCAL_DATA_ZIP, "rb") as f:
                data = f.read()
            buf = io.BytesIO(data)
            with zipfile.ZipFile(buf) as z:
                names = [n for n in z.namelist() if n.endswith(".csv")]
            if names:
                csvs = (data, names)
                process_error = None  # Clear error since we found a source
            else:
                process_error = f"No CSV files found in local zip {LOCAL_DATA_ZIP}"
        except Exception as e:
            process_error = f"Could not read local zip {LOCAL_DATA_ZIP}: {str(e)}"

    # Process ZIP files (remote or local)
    if csvs:
        data, names = csvs
        # Deduplicate files - keep only highest second row number for duplicates
        names = deduplicate_files(names)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as z:
            for name in names:
                if not FILENAME_RE.match(name):
                    print(f"Skipping unexpected file: {name}")
                    continue
                with z.open(name) as fh:
                    # wrap bytes in text IO for csv
                    textf = io.TextIOWrapper(fh, encoding="utf-8", newline="")
                    reader = csv.DictReader(textf)
                    process_csv(reader, name, usage)
    else:
        # Fallback: read local files from LOCAL_USAGE_OUTPUT_DIR
        file_paths = list(LOCAL_USAGE_OUTPUT_DIR.glob("icd10_*.csv"))
        file_names = [fpath.name for fpath in file_paths]
        # Deduplicate file names
        deduplicated_names = deduplicate_files(file_names)
        deduplicated_set = set(deduplicated_names)

        for fpath in file_paths:
            if fpath.name not in deduplicated_set:
                continue
            if not FILENAME_RE.match(fpath.name):
                print(f"Skipping unexpected file: {fpath}")
                continue

            with open(fpath, newline="") as fh:
                process_csv(csv.DictReader(fh), fpath.name, usage)

    return usage, process_error


def find_missing_and_unused_codes():
    """Find codes missing from OCL and codes unused in practice."""
    ocl_codes = load_ocl_codes()
    usage, process_error = load_code_usage_data()

    all_used_codes = {
        "apcs": set(usage["apcs"].keys()),
        "ons_deaths": set(usage["ons_deaths"].keys()),
    }

    missing_from_ocl = {
        "apcs": all_used_codes["apcs"] - ocl_codes["apcs"],
        "ons_deaths": all_used_codes["ons_deaths"] - ocl_codes["ons_deaths"],
    }

    # Get counts for missing codes
    missing_code_count_dict = {"apcs": {}, "ons_deaths": {}}
    for code in missing_from_ocl["apcs"]:
        missing_code_count_dict["apcs"][code] = usage["apcs"][code]
    for code in missing_from_ocl["ons_deaths"]:
        missing_code_count_dict["ons_deaths"][code] = usage["ons_deaths"][code]

    unused_in_practice = {
        "apcs": set(),
        "ons_deaths": set(),
    }
    for code in ocl_codes["apcs"]:
        if code not in all_used_codes["apcs"]:
            unused_in_practice["apcs"].add(code)
    for code in ocl_codes["ons_deaths"]:
        if code not in all_used_codes["ons_deaths"]:
            unused_in_practice["ons_deaths"].add(code)

    return missing_code_count_dict, unused_in_practice, usage, process_error


def main():
    missing_from_ocl, unused_in_practice, usage, process_error = (
        find_missing_and_unused_codes()
    )

    # Ensure output directory exists
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize warning messages
    csv_warning = ""

    if process_error:
        csv_warning = (
            "# WARNING: Remote ZIP unavailable. Using local test data from `output/`.\n"
            "# This file was produced from local outputs because the remote ZIP could not be downloaded.\n"
            f"# Error message: {process_error}\n"
        )

    # Write combined APCS usage single file
    with open(OUT_DIR / "code_usage_combined_apcs.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "icd10_code",
                "financial_year",
                "apcs_primary_count",
                "apcs_secondary_count",
                "apcs_all_count",
                "in_opencodelists",
            ]
        )
        for code in sorted(usage["apcs"].keys()):
            for financial_year, counts in usage["apcs"][code].items():
                writer.writerow(
                    [
                        code,
                        financial_year,
                        counts.get("apcs_primary_count", "0"),
                        counts.get("apcs_secondary_count", "0"),
                        counts.get("apcs_all_count", "0"),
                        "yes" if code not in missing_from_ocl["apcs"] else "no",
                    ]
                )
    # Write combined ONS deaths usage single file
    with open(OUT_DIR / "code_usage_combined_ons_deaths.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "icd10_code",
                "financial_year",
                "ons_primary_count",
                "ons_contributing_count",
                "in_opencodelists",
            ]
        )
        for code in sorted(usage["ons_deaths"].keys()):
            for financial_year, counts in usage["ons_deaths"][code].items():
                writer.writerow(
                    [
                        code,
                        financial_year,
                        counts.get("ons_primary_count", "0"),
                        counts.get("ons_contributing_count", "0"),
                        "yes" if code not in missing_from_ocl["ons_deaths"] else "no",
                    ]
                )

    # Write OCL codes not appearing in apcs usage
    with open(OUT_DIR / "ocl_codes_not_in_apcs.csv", "w", newline="") as f:
        f.write(csv_warning)
        writer = csv.writer(f)
        writer.writerow(["icd10_code"])
        for code in sorted(unused_in_practice["apcs"]):
            writer.writerow([code])
    # Write OCL codes not appearing in ons deaths usage
    with open(OUT_DIR / "ocl_codes_not_in_ons_deaths.csv", "w", newline="") as f:
        f.write(csv_warning)
        writer = csv.writer(f)
        writer.writerow(["icd10_code"])
        for code in sorted(unused_in_practice["ons_deaths"]):
            writer.writerow([code])


if __name__ == "__main__":
    main()
