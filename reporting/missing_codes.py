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


# safe paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "reporting" / "data"
OUT_DIR = REPO_ROOT / "reporting" / "outputs"
OCL_ICD10_2019_CODES_FILE = DATA_DIR / "ocl_icd10_codes.txt"

# Precompiled regexes used by multiple functions
FILENAME_RE = re.compile(r"icd10_(apcs|ons_deaths)_[0-9]{4}_[0-9]{2}.*\.csv")
FY_RE = re.compile(r"_(\d{4}_\d{2})")


def load_ocl_codes() -> set:
    """Load all ICD10 codes from OpenCodelists export."""
    ocl_codes = set()
    with open(OCL_ICD10_2019_CODES_FILE) as f:
        for line in f:
            code = line.strip()
            if code:
                ocl_codes.add(code)

    # Should be at least 12,000
    assert len(ocl_codes) >= 12000, "Loaded too few ICD10 codes from OCL"

    # Should contain some known codes
    for known_code in ["A00", "B99", "C341", "E119", "I10", "J459", "Z992"]:
        assert known_code in ocl_codes, (
            f"Known ICD10 code {known_code} missing from OCL codes"
        )
    return ocl_codes


# In dev mode load the code usage from local files
LOCAL_USAGE_OUTPUT_DIR = REPO_ROOT / "output"


def fy_from_filename(name: str) -> str:
    """Extract canonical financial-year string (e.g. '2024-25') from filename."""
    m = FY_RE.search(name)
    assert m, f"Could not extract financial year from filename: {name}"
    return m.group(1).replace("_", "-")


def process_csv(reader, name, usage):
    """Populate usage from a csv.DictReader and filename."""
    financial_year = fy_from_filename(name)
    is_apcs = "apcs" in name
    for row in reader:
        code = (row.get("icd10_code") or "").strip()
        assert code, f"Empty icd10_code in file {name}"
        u = usage[code][financial_year]
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

    Tries to download the remote ZIP file, if that fails falls
    back to local files produced by running the tests

    Returns a mapping: code -> { financial_year -> { counts } }
    """
    usage = defaultdict(lambda: defaultdict(dict))

    # Attempt to download zip from remote
    remote_url = "https://jobs.opensafely.org/opensafely-internal/tpp-code-counts/outputs/latest/download/"
    csvs = None
    process_error = None
    try:
        with urllib.request.urlopen(remote_url, timeout=20) as resp:
            data = resp.read()
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as z:
            names = [n for n in z.namelist() if n.endswith(".csv")]
        if names:
            csvs = (data, names)
        else:
            process_error = f"No CSV files found in zip file from {remote_url}"
    except Exception as e:
        process_error = str(e)

    if csvs:
        data, names = csvs
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
        for fpath in LOCAL_USAGE_OUTPUT_DIR.glob("icd10_*.csv"):
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

    all_used_codes = set(usage.keys())

    missing_from_ocl = all_used_codes - ocl_codes
    unused_in_practice = ocl_codes - all_used_codes

    # Get counts for missing codes
    missing_code_count_dict = {}
    for code in missing_from_ocl:
        missing_code_count_dict[code] = usage[code]

    return missing_code_count_dict, unused_in_practice, usage, process_error


def main():
    missing_from_ocl, unused_in_practice, usage, process_error = (
        find_missing_and_unused_codes()
    )

    # Ensure output directory exists
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if process_error:
        csv_warning = (
            "# WARNING: Remote ZIP unavailable. Using local test data from `output/`.\n"
            "# This file was produced from local outputs because the remote ZIP could not be downloaded.\n"
            f"# Remote download error: {process_error}\n"
        )
        md_warning = (
            "# WARNING\n\n"
            "**This report was generated using local test data from `output/` because the remote ZIP could not be downloaded.**\n\n"
            f"Remote download error: {process_error}\n\n"
        )

    # Write combined usage single file
    with open(OUT_DIR / "code_usage_combined.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "icd10_code",
                "financial_year",
                "apcs_primary_count",
                "apcs_secondary_count",
                "apcs_all_count",
                "ons_primary_count",
                "ons_contributing_count",
            ]
        )
        for code in sorted(usage):
            for financial_year, counts in usage[code].items():
                writer.writerow(
                    [
                        code,
                        financial_year,
                        counts.get("apcs_primary_count", "0"),
                        counts.get("apcs_secondary_count", "0"),
                        counts.get("apcs_all_count", "0"),
                        counts.get("ons_primary_count", "0"),
                        counts.get("ons_contributing_count", "0"),
                    ]
                )

    # Write unused codes CSV
    with open(OUT_DIR / "unused_codes.csv", "w", newline="") as f:
        f.write(csv_warning)
        writer = csv.writer(f)
        writer.writerow(["icd10_code"])
        for code in sorted(unused_in_practice):
            writer.writerow([code])

    # Write missing codes CSV
    with open(OUT_DIR / "missing_codes.csv", "w", newline="") as f:
        f.write(csv_warning)
        writer = csv.writer(f)
        writer.writerow(
            [
                "icd10_code",
                "financial_year",
                "apcs_primary_count",
                "apcs_secondary_count",
                "apcs_all_count",
                "ons_primary_count",
                "ons_contributing_count",
            ]
        )
        for code in sorted(missing_from_ocl):
            for financial_year, counts in missing_from_ocl[code].items():
                writer.writerow(
                    [
                        code,
                        financial_year,
                        counts.get("apcs_primary_count", "0"),
                        counts.get("apcs_secondary_count", "0"),
                        counts.get("apcs_all_count", "0"),
                        counts.get("ons_primary_count", "0"),
                        counts.get("ons_contributing_count", "0"),
                    ]
                )

    # Write markdown report
    with open(OUT_DIR / "missing_codes_report.md", "w") as f:
        f.write(md_warning)
        f.write(
            "# Report on ICD10 Codes Missing from OpenCodelists and Unused in Practice\n\n"
        )
        f.write("## ICD10 Codes Missing from OpenCodelists:\n\n")
        f.write(
            "| Code | Financial Year | APCS Primary Count | APCS Secondary Count | APCS All Count | ONS Primary Count | ONS Contributing Count |\n"
        )
        f.write(
            "|------|----------------|--------------------|----------------------|----------------|-------------------|-----------------------|\n"
        )
        for code in sorted(missing_from_ocl):
            for financial_year, counts in missing_from_ocl[code].items():
                f.write(
                    f"| {code} | {financial_year} | {counts.get('apcs_primary_count', '0')} | {counts.get('apcs_secondary_count', '0')} | {counts.get('apcs_all_count', '0')} | {counts.get('ons_primary_count', '0')} | {counts.get('ons_contributing_count', '0')} |\n"
                )

        f.write("\n## ICD10 Codes Unused in Practice:\n\n")
        f.write(
            "The following are the first 50 ICD10 codes present in OpenCodelists but not used in practice:\n\n"
        )
        for code in sorted(unused_in_practice)[:50]:
            f.write(f"{code}\n")


if __name__ == "__main__":
    main()
