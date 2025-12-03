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
ICD10_PATTERN = re.compile(r"^[A-Z][0-9]{2}\.?[0-9X]?[0-9]?[*|]?$")

# Valid financial year patterns:
# - canonical format required: "2024-25" (YYYY-YY)
FY_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def is_valid(value, pattern):
    """Check if value matches pattern (blank/NULL always valid)."""
    v = (value or "").strip().upper()
    return v == "" or v == "NULL" or pattern.match(v)


def validate_file(filepath):
    """Validate a CSV file, returning sets of invalid values plus stats."""
    invalid_icd10 = set()
    invalid_fy = set()
    row_count = 0
    missing = False

    try:
        with open(filepath) as f:
            for row in csv.DictReader(f):
                row_count += 1
                code = row.get("icd10_code", "")
                fy = row.get("financial_year", "")

                if not is_valid(code, ICD10_PATTERN):
                    invalid_icd10.add(code.strip())
                if not is_valid(fy, FY_PATTERN):
                    invalid_fy.add(fy.strip())

        # Get file size in bytes
        file_size_bytes = Path(filepath).stat().st_size
    except FileNotFoundError:
        missing = True
        file_size_bytes = 0

    return invalid_icd10, invalid_fy, row_count, file_size_bytes, missing


def format_bullet_list(items):
    if not items:
        return "None"
    return "\n" + "\n".join(f"    - {item}" for item in sorted(items))


def format_markdown_bullet_list(items):
    if not items:
        return "None"
    return "\n" + "\n".join(f"- `{item}`" for item in sorted(items))


def write_invalid_icd10_rows(input_path: str, source: str):
    """Write rows with invalid ICD10 codes from input CSV to a new CSV.

    Keeps the original columns (including financial_year).
    Returns filepath and number of rows written.
    """
    p = Path(input_path)
    outfile = Path("output") / f"icd10_{source}_invalid_rows.csv"
    if not p.exists():
        return str(outfile), 0

    with open(p) as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows_written = 0
        outfile.parent.mkdir(parents=True, exist_ok=True)
        with open(outfile, "w", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=header)
            writer.writeheader()
            for row in reader:
                code = row.get("icd10_code", "")
                if not is_valid(code, ICD10_PATTERN):
                    writer.writerow(row)
                    rows_written += 1

    return str(outfile), rows_written


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
            outfile = Path("output") / f"icd10_{source}_unknown_financial_year.csv"
        else:
            outfile = Path("output") / f"icd10_{source}_{slug}.csv"
        outfile.parent.mkdir(parents=True, exist_ok=True)
        # derive header; keep 'financial_year' for the unknown slug
        if slug == "unknown":
            out_header = list(header)
        else:
            out_header = [c for c in header if c != "financial_year"]
        # If header is empty (some broken files), fall back to keys of first row
        if not out_header and rows:
            out_header = [k for k in rows[0].keys() if k != "financial_year"]
        with open(outfile, "w", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=out_header)
            writer.writeheader()
            for row in rows:
                if slug == "unknown":
                    # Ensure the raw financial year is present in the 'financial_year' column.
                    raw_fy = (row.get("financial_year") or "").strip()
                    out_row = dict(row)
                    out_row["financial_year"] = raw_fy
                else:
                    out_row = {k: v for k, v in row.items() if k != "financial_year"}
                writer.writerow(out_row)
        created.append((str(outfile), len(rows)))

    return created


def main():
    apcs_icd10, apcs_fy, apcs_rows, apcs_size_bytes, apcs_missing = validate_file(
        "output/icd10_apcs.csv"
    )
    ons_icd10, ons_fy, ons_rows, ons_size_bytes, ons_missing = validate_file(
        "output/icd10_ons_deaths.csv"
    )

    # Split files per financial year and record created files/collisions
    apcs_created = split_by_financial_year("output/icd10_apcs.csv", "apcs")
    ons_created = split_by_financial_year("output/icd10_ons_deaths.csv", "ons_deaths")

    # Write invalid rows files
    apcs_invalid_path, apcs_invalid_rows = write_invalid_icd10_rows(
        "output/icd10_apcs.csv", "apcs"
    )
    ons_invalid_path, ons_invalid_rows = write_invalid_icd10_rows(
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
        f"  Invalid rows (invalid ICD10) file: {apcs_invalid_path} ({apcs_invalid_rows:,} rows)",
        f"  Invalid financial years: {format_bullet_list(apcs_fy)}",
        "",
        "ONS Deaths:",
        f"  File size: {format_size(ons_size_bytes)}",
        f"  Rows: {ons_rows:,}",
        f"  Invalid rows (invalid ICD10) file: {ons_invalid_path} ({ons_invalid_rows:,} rows)",
        f"  Invalid financial years: {format_bullet_list(ons_fy)}",
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
