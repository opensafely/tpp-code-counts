"""
Validate output from ICD10 code counting queries.

Checks:
1. ICD10 codes match expected formats (or are blank/NULL)
2. Financial years match expected formats (or are blank/NULL)

Produces a short report with findings.
"""

import csv
import re


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
    """Validate a CSV file, returning sets of invalid values."""
    invalid_icd10 = set()
    invalid_fy = set()

    with open(filepath) as f:
        for row in csv.DictReader(f):
            code = row.get("icd10_code", "")
            fy = row.get("financial_year", "")

            if not is_valid(code, ICD10_PATTERN):
                invalid_icd10.add(code.strip())
            if not is_valid(fy, FY_PATTERN):
                invalid_fy.add(fy.strip())

    return invalid_icd10, invalid_fy


def format_bullet_list(items):
    if not items:
        return "None"
    return "\n" + "\n".join(f"    - {item}" for item in sorted(items))


def main():
    apcs_icd10, apcs_fy = validate_file("output/icd10_apcs.csv")
    ons_icd10, ons_fy = validate_file("output/icd10_ons_deaths.csv")

    lines = [
        "=" * 60,
        "ICD10 CODE OUTPUT VALIDATION REPORT",
        "=" * 60,
        "",
        "HES APCS:",
        f"  Invalid ICD10 codes: {format_bullet_list(apcs_icd10)}",
        f"  Invalid financial years: {format_bullet_list(apcs_fy)}",
        "",
        "ONS Deaths:",
        f"  Invalid ICD10 codes: {format_bullet_list(ons_icd10)}",
        f"  Invalid financial years: {format_bullet_list(ons_fy)}",
    ]

    report = "\n".join(lines)

    with open("output/validation_report.txt", "w") as f:
        f.write(report)


if __name__ == "__main__":
    main()
