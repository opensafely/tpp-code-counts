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
ICD10_PATTERN = re.compile(r"^[A-Z][0-9]{2}\.?[0-9X]?[0-9]?$")

# Valid financial year patterns:
# - "2024-25" format
# - "202425" format
FY_PATTERN = re.compile(r"^(\d{4}-\d{2}|\d{6})$")


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


def format_size(bytes_count: int) -> str:
    """Return human friendly size string for byte count."""
    if bytes_count >= 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.2f} MB"
    if bytes_count >= 1024:
        return f"{bytes_count / 1024:.2f} KB"
    return f"{bytes_count} B"


def main():
    apcs_icd10, apcs_fy, apcs_rows, apcs_size_bytes, apcs_missing = validate_file(
        "output/icd10_apcs.csv"
    )
    ons_icd10, ons_fy, ons_rows, ons_size_bytes, ons_missing = validate_file(
        "output/icd10_ons_deaths.csv"
    )

    # Build a Markdown report
    md_lines = []
    md_lines.append("# ICD10 CODE OUTPUT VALIDATION REPORT\n")

    # Summary table
    md_lines.append("## Summary\n")
    md_lines.append("| Source | File | Size (MB) | Rows |")
    md_lines.append("| --- | --- | ---: | ---: |")
    md_lines.append(
        f"| HES APCS | output/icd10_apcs.csv {'(missing)' if apcs_missing else ''} | {format_size(apcs_size_bytes)} | {apcs_rows:,} |"
    )
    md_lines.append(
        f"| ONS Deaths | output/icd10_ons_deaths.csv {'(missing)' if ons_missing else ''} | {format_size(ons_size_bytes)} | {ons_rows:,} |\n"
    )

    # HES APCS details
    md_lines.append("## HES APCS\n")
    md_lines.append(
        f"**File size:** {format_size(apcs_size_bytes)}  {'(missing)' if apcs_missing else ''}"
    )
    md_lines.append(f"**Rows:** {apcs_rows:,}  \n")
    md_lines.append("**Invalid ICD10 codes:**\n")
    md_lines.append(format_markdown_bullet_list(apcs_icd10) + "\n")
    md_lines.append("**Invalid financial years:**\n")
    md_lines.append(format_markdown_bullet_list(apcs_fy) + "\n")

    # ONS Deaths details
    md_lines.append("## ONS Deaths\n")
    md_lines.append(
        f"**File size:** {format_size(ons_size_bytes)}  {'(missing)' if ons_missing else ''}"
    )
    md_lines.append(f"**Rows:** {ons_rows:,}  \n")
    md_lines.append("**Invalid ICD10 codes:**\n")
    md_lines.append(format_markdown_bullet_list(ons_icd10) + "\n")
    md_lines.append("**Invalid financial years:**\n")
    md_lines.append(format_markdown_bullet_list(ons_fy) + "\n")

    report_md = "\n".join(md_lines)

    with open("output/validation_report.md", "w") as f:
        f.write(report_md)

    # Also write a plain text report for compatibility
    with open("output/validation_report.txt", "w") as f:
        f.write(report_md.replace("\n", "\n"))


if __name__ == "__main__":
    main()
