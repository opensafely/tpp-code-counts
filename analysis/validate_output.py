"""
Validate output from ICD10 code counting queries.

Checks:
1. ICD10 codes match expected formats (or are blank/NULL)
2. Financial years match expected formats (or are blank/NULL)
3. File sizes in MB
4. Number of rows in each file

Produces a short report with findings.
"""

import csv
import re
from pathlib import Path


# Valid ICD10 code patterns:
# - A00 (3 chars)
# - A00.0 or A00.X (5 chars with dot)
# - A000 or A00X (4 chars without dot)
# - A00.00 or A00.X0 (6 chars with dot)
# - A0000 or A00X0 (5 chars without dot)

# - Codes with a trailing "*" (asterisk codes in ICD10)
# - Codes with a trailing "|" (dagger codes in ICD10)
# - Codes with a trailing "~" (seen a lot in data before 2023)
ICD10_PATTERN = re.compile(r"^[A-Z][0-9]{2}\.?[0-9X]?[0-9]?[*|~]?$")

# Valid financial year patterns:
# - canonical format required: "2024-25" (YYYY-YY)
FY_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def is_valid(value, pattern):
    """Check if value matches pattern (blank/NULL always valid)."""
    v = (value or "").strip().upper()
    return v == "" or v == "NULL" or pattern.match(v)


def validate_file(filepath):
    """Validate a CSV file, returning stats."""
    invalid_fy = set()
    row_count = 0

    try:
        with open(filepath) as f:
            for row in csv.DictReader(f):
                row_count += 1
                fy = row.get("financial_year", "")

                if not is_valid(fy, FY_PATTERN):
                    invalid_fy.add(fy.strip())

        # Get file size in bytes
        file_size_bytes = Path(filepath).stat().st_size
    except FileNotFoundError:
        file_size_bytes = 0

    return invalid_fy, row_count, file_size_bytes


def format_bullet_list(items):
    if not items:
        return "None"
    return "\n" + "\n".join(f"    - {item}" for item in sorted(items))


def format_markdown_bullet_list(items):
    if not items:
        return "None"
    return "\n" + "\n".join(f"- `{item}`" for item in sorted(items))


def write_partitioned_csv(header: list, outfile_base: str, rows: list):
    """Write `rows` (list of dict) to CSV(s) with header.

    outfile_base is a string representing the desired filename
    for a single file. If the total row count including header would be >= 5000
    then the output will be partitioned into files of at most 4,990 rows
    (including header) to stay safely under the 5,000-row threshold.

    Returns a list of tuples: [(filepath, data_rows_written), ...].
    """
    # Threshold behaviour
    MAX_TOTAL_ROWS = 5000
    MAX_TOTAL_ROWS_SAFE = MAX_TOTAL_ROWS - 10  # leave some margin

    total_rows_including_header = len(rows) + 1
    if total_rows_including_header < MAX_TOTAL_ROWS:
        # single file
        out_file = Path("output") / f"{outfile_base}.csv"
        with open(out_file, "w", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=header)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return [(str(out_file), len(rows))]

    # Partition into chunks of MAX_TOTAL_ROWS_SAFErows
    created = []
    current_start = 1  # original-file row number for header is 1
    for i in range(0, len(rows), MAX_TOTAL_ROWS_SAFE):
        chunk = rows[i : i + MAX_TOTAL_ROWS_SAFE]
        chunk_len = len(chunk)
        chunk_start = current_start
        chunk_end = current_start + chunk_len
        suffix = f"_rows_{chunk_start:04d}_{chunk_end:04d}"
        partition_path = Path("output") / f"{outfile_base}{suffix}.csv"
        with open(partition_path, "w", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=header)
            writer.writeheader()
            for row in chunk:
                writer.writerow(row)
        created.append((str(partition_path), chunk_len))
        current_start = chunk_end + 1

    return created


def write_invalid_icd10_rows(input_path: str, source: str):
    """Write rows with invalid ICD10 codes from input CSV to a new CSV.

    Keeps the original columns (including financial_year).
    Returns filepath and number of rows written.
    """
    p = Path(input_path)
    if not p.exists():
        return []

    with open(p) as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = [
            row
            for row in reader
            if not is_valid(row.get("icd10_code", ""), ICD10_PATTERN)
        ]

    if not rows:
        return []

    # Use partitioned writer
    created = write_partitioned_csv(header, f"icd10_{source}_invalid_rows", rows)
    return created


def format_size(bytes_count: int) -> str:
    """Return human friendly size string for byte count."""
    if bytes_count >= 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.2f} MB"
    if bytes_count >= 1024:
        return f"{bytes_count / 1024:.2f} KB"
    return f"{bytes_count} B"


def normalize_fy(raw_fy: str):
    """Return raw FY if it matches 'YYYY-YY', otherwise None."""
    if not raw_fy:
        return None
    s = str(raw_fy).strip()
    return s if FY_PATTERN.match(s) else None


def slugify_fy(raw_fy: str) -> str:
    """Return safe slug for FY for file naming, e.g. '2024-25' -> '2024_25'.

    If raw_fy is None or can't normalize, return 'unknown'.
    """
    normalized = normalize_fy(raw_fy)
    if not normalized:
        return "unknown"
    # Replace separator with underscore
    return normalized.replace("-", "_")


def split_by_financial_year(input_path: str, source: str):
    """Split a CSV file by financial year and return created file info

    Returns created_files: list[(outfile, rows)]
    """
    created = []
    p = Path(input_path)
    if not p.exists():
        return created

    with open(p) as f:
        reader = csv.DictReader(f)
        rows_by_slug = {}
        slug_to_raws = {}
        header = reader.fieldnames or []
        for row in reader:
            raw_fy = row.get("financial_year", "")
            code = (row.get("icd10_code", "") or "").strip()
            slug = slugify_fy(raw_fy)
            # Only include rows with valid ICD10 in per-FY splits. Invalid rows
            # are collected separately by write_invalid_icd10_rows().
            if is_valid(code, ICD10_PATTERN):
                rows_by_slug.setdefault(slug, []).append(row)
            slug_to_raws.setdefault(slug, set()).add((raw_fy or "").strip())

    # Write out one CSV file per slug, removing 'financial_year' column
    for slug, rows in rows_by_slug.items():
        if slug == "unknown":
            outfile_base = f"icd10_{source}_unknown_financial_year"
        else:
            outfile_base = f"icd10_{source}_{slug}"
        # derive header; keep 'financial_year' for the unknown slug
        if slug == "unknown":
            out_header = list(header)
        else:
            out_header = [c for c in header if c != "financial_year"]
        # If header is empty (some broken files), fall back to keys of first row
        if not out_header and rows:
            out_header = [k for k in rows[0].keys() if k != "financial_year"]

        # Build output rows according to whether we keep financial_year
        out_rows = []
        for row in rows:
            if slug == "unknown":
                raw_fy = (row.get("financial_year") or "").strip()
                out_row = dict(row)
                out_row["financial_year"] = raw_fy
            else:
                out_row = {k: v for k, v in row.items() if k != "financial_year"}
            out_rows.append(out_row)

        # Write files (partitioned if necessary)
        created_files = write_partitioned_csv(out_header, outfile_base, out_rows)
        for fpath, rows_written in created_files:
            created.append((fpath, rows_written))

    return created


def main():
    apcs_fy, apcs_rows, apcs_size_bytes = validate_file("output/icd10_apcs.csv")
    ons_fy, ons_rows, ons_size_bytes = validate_file("output/icd10_ons_deaths.csv")

    # Split files per financial year and record created files/collisions
    apcs_created = split_by_financial_year("output/icd10_apcs.csv", "apcs")
    ons_created = split_by_financial_year("output/icd10_ons_deaths.csv", "ons_deaths")

    # Write invalid rows files
    invalid_apcs_files = write_invalid_icd10_rows("output/icd10_apcs.csv", "apcs")
    invalid_ons_files = write_invalid_icd10_rows(
        "output/icd10_ons_deaths.csv", "ons_deaths"
    )

    lines = [
        "=" * 60,
        "ICD10 CODE OUTPUT VALIDATION REPORT",
        "=" * 60,
        "",
        "HES APCS:",
        f"  File size: {format_size(apcs_size_bytes)}",
        f"  Rows: {apcs_rows:,}",
        f"  Invalid financial years: {format_bullet_list(apcs_fy)}",
        f"  Files created: {format_bullet_list([f for f, _ in apcs_created + invalid_apcs_files])}",
        "",
        "ONS Deaths:",
        f"  File size: {format_size(ons_size_bytes)}",
        f"  Rows: {ons_rows:,}",
        f"  Invalid financial years: {format_bullet_list(ons_fy)}",
        f"  Files created: {format_bullet_list([f for f, _ in ons_created + invalid_ons_files])}",
        "",
    ]

    # List per-FY created files in the report
    if apcs_created:
        lines.append("")
        lines.append("HES APCS per-FY files:")
        for fpath, rows in sorted(apcs_created):
            lines.append(f"  - {fpath}: {rows:,} rows")
    if ons_created:
        lines.append("")
        lines.append("ONS Deaths per-FY files:")
        for fpath, rows in sorted(ons_created):
            lines.append(f"  - {fpath}: {rows:,} rows")

    report = "\n".join(lines)

    with open("output/validation_report.txt", "w") as f:
        f.write(report)


if __name__ == "__main__":
    main()
