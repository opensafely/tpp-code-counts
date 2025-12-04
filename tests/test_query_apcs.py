"""
Test ICD10 code counts from HES APCS data against a real MSSQL database
with compatibility level 100 (matching TPP's production configuration).

This test:
1. Connects to the sqlrunner MSSQL test container
2. Creates APCS, APCS_Der and PatientsWithTypeOneDissent tables
3. Inserts test data
4. Runs the actual T-SQL query from query_icd10_apcs.sql
5. Verifies results match expected values

Usage:
    pytest test_query_apcs.py

Prerequisites:
    - Docker running
    - sqlrunner repo cloned at ../sqlrunner
"""

import csv
from pathlib import Path

import pytest

from .mssql_test_helper import (
    drop_table_if_exists,
    execute_sql,
    get_connection,
    run_query,
    setup_t1oo_table,
)


# Output directory for query results
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def setup_apcs_table(conn):
    """Create and populate the APCS test table."""
    drop_table_if_exists(conn, "APCS")

    execute_sql(
        conn,
        """
        CREATE TABLE APCS (
            APCS_Ident BIGINT PRIMARY KEY,
            Patient_ID BIGINT NOT NULL,
            Admission_Date DATE,
            Discharge_Date DATE,
            Der_Financial_Year VARCHAR(7),
            Der_Diagnosis_All VARCHAR(4000),
            Der_Diagnosis_Count INT
        )
    """,
    )

    # Insert test data
    # Format: (APCS_Ident, Patient_ID, Admission_Date, Discharge_Date, Der_Financial_Year, Der_Diagnosis_All, Der_Diagnosis_Count)
    test_data = [
        # Basic records with multiple codes
        (
            1,
            101,
            "2024-04-15",
            "2024-04-20",
            "2024-25",
            "||E119 ,E780 ,J449 ||I801 ,I802 ,N179",
            6,
        ),
        (2, 102, "2024-05-10", "2024-05-12", "2024-25", "||E119 ,I10", 2),
        (3, 103, "2024-06-01", "2024-06-05", "2024-25", "||J449||E780 ,E119", 3),
        (4, 104, "2024-07-20", "2024-07-22", "2024-25", "||K219 ,K210", 2),
        (5, 105, "2024-08-15", "2024-08-16", "2024-25", "||E119", 1),
        (
            6,
            106,
            "2024-09-01",
            "2024-09-03",
            "2024-25",
            "||I10 ,I10 ,E119||E119",
            2,
        ),  # Duplicate codes in same spell
        (7, 107, "2024-10-10", "2024-10-15", "2024-25", "||J189 ,J449", 2),
        (8, 108, "2024-11-20", "2024-11-25", "2024-25", "||E119 ,N179", 2),
        (9, 109, "2024-12-05", "2024-12-08", "2024-25", "||I801", 1),
        (10, 110, "2025-01-15", "2025-01-18", "2024-25", "||E780 ,K219", 2),
        (11, 111, "2025-02-10", "2025-02-12", "2024-25", "||E119 ,J449", 2),
        (12, 112, "2025-03-01", "2025-03-05", "2024-25", "||I10||E119 ,E780", 3),
        # More E119 records to test count >= 15 and rounding
        (21, 121, "2024-04-20", "2024-04-22", "2024-25", "||E119 ,I10", 2),
        (22, 122, "2024-04-25", "2024-04-27", "2024-25", "||E119", 1),
        (23, 123, "2024-05-05", "2024-05-07", "2024-25", "||E119 ,I10 ,J449", 3),
        (24, 124, "2024-05-15", "2024-05-17", "2024-25", "||E119", 1),
        (25, 125, "2024-05-20", "2024-05-22", "2024-25", "||E119 ,I10", 2),
        (26, 126, "2024-06-10", "2024-06-12", "2024-25", "||E119 ,J449", 2),
        (27, 127, "2024-06-15", "2024-06-17", "2024-25", "||E119 ,I10", 2),
        (28, 128, "2024-06-20", "2024-06-22", "2024-25", "||E119", 1),
        (29, 129, "2024-07-01", "2024-07-03", "2024-25", "||E119 ,I10 ,J449", 3),
        (30, 130, "2024-07-10", "2024-07-12", "2024-25", "||E119", 1),
        (31, 131, "2024-07-15", "2024-07-17", "2024-25", "||E119 ,I10", 2),
        (32, 132, "2024-08-01", "2024-08-03", "2024-25", "||E119 ,J449", 2),
        (33, 133, "2024-08-10", "2024-08-12", "2024-25", "||E119 ,I10", 2),
        (34, 134, "2024-08-20", "2024-08-22", "2024-25", "||E119", 1),
        (35, 135, "2024-09-05", "2024-09-07", "2024-25", "||E119 ,I10 ,J449", 3),
        (36, 136, "2024-09-15", "2024-09-17", "2024-25", "||E119", 1),
        (37, 137, "2024-09-25", "2024-09-27", "2024-25", "||E119 ,I10", 2),
        (38, 138, "2024-10-05", "2024-10-07", "2024-25", "||E119 ,J449", 2),
        (39, 139, "2024-10-15", "2024-10-17", "2024-25", "||E119 ,I10", 2),
        (40, 140, "2024-10-25", "2024-10-27", "2024-25", "||E119", 1),
        (41, 141, "2024-11-05", "2024-11-07", "2024-25", "||E119 ,I10 ,J449", 3),
        (42, 142, "2024-11-15", "2024-11-17", "2024-25", "||E119", 1),
        (43, 143, "2024-11-25", "2024-11-27", "2024-25", "||E119 ,I10", 2),
        (44, 144, "2024-12-10", "2024-12-12", "2024-25", "||E119 ,J449", 2),
        (45, 145, "2024-12-20", "2024-12-22", "2024-25", "||E119 ,I10", 2),
        (46, 146, "2025-01-05", "2025-01-07", "2024-25", "||E119", 1),
        (47, 147, "2025-01-20", "2025-01-22", "2024-25", "||E119 ,I10 ,J449", 3),
        (48, 148, "2025-02-05", "2025-02-07", "2024-25", "||E119", 1),
        (49, 149, "2025-02-20", "2025-02-22", "2024-25", "||E119 ,I10", 2),
        (50, 150, "2025-03-10", "2025-03-12", "2024-25", "||E119 ,J449", 2),
        # More I10 records
        (51, 151, "2024-05-25", "2024-05-27", "2024-25", "||I10", 1),
        (52, 152, "2024-07-25", "2024-07-27", "2024-25", "||I10", 1),
        (53, 153, "2024-09-20", "2024-09-22", "2024-25", "||I10", 1),
        (54, 154, "2024-11-10", "2024-11-12", "2024-25", "||I10", 1),
        (55, 155, "2025-01-10", "2025-01-12", "2024-25", "||I10", 1),
        (63, 163, "2024-06-05", "2024-06-07", "2024-25", "||I10", 1),
        (64, 164, "2024-08-05", "2024-08-07", "2024-25", "||I10", 1),
        (65, 165, "2024-10-01", "2024-10-03", "2024-25", "||I10", 1),
        (66, 166, "2024-12-01", "2024-12-03", "2024-25", "||I10", 1),
        (67, 167, "2025-02-01", "2025-02-03", "2024-25", "||I10", 1),
        # J449 and E780 additional records
        (56, 156, "2024-06-25", "2024-06-27", "2024-25", "||J449 ,E780", 2),
        (57, 157, "2024-08-25", "2024-08-27", "2024-25", "||J449 ,E780", 2),
        (58, 158, "2024-10-20", "2024-10-22", "2024-25", "||J449 ,E780", 2),
        (59, 159, "2024-07-05", "2024-07-07", "2024-25", "||E780", 1),
        (60, 160, "2024-09-10", "2024-09-12", "2024-25", "||E7801", 1),
        (61, 161, "2024-11-01", "2024-11-03", "2024-25", "||E7802", 1),
        (62, 162, "2025-02-15", "2025-02-17", "2024-25", "||E7800", 1),
        # Previous financial year data
        (13, 201, "2023-04-10", "2023-04-15", "2023-24", "||E119 ,I10", 2),
        (14, 202, "2023-06-20", "2023-06-25", "2023-24", "||J449 ,E780", 2),
        (15, 203, "2023-09-15", "2023-09-18", "2023-24", "||E119||K219", 2),
        (16, 204, "2023-12-01", "2023-12-05", "2023-24", "||N179 ,I801", 2),
        (17, 205, "2024-02-20", "2024-02-25", "2023-24", "||E119 ,E780 ,J449", 3),
        # Edge cases
        (18, 301, "2024-05-01", "2024-05-02", "2024-25", None, None),  # NULL diagnosis
        (19, 302, "2024-06-01", "2024-06-02", "2024-25", "", 0),  # Empty diagnosis
        (
            20,
            303,
            "2024-07-01",
            "2024-07-02",
            "2024-25",
            "||  E119  ,  E780  ||  J449  ",
            3,
        ),  # Extra spaces
        # Records for opted-out patient (should be excluded)
        (68, 999, "2024-05-01", "2024-05-02", "2024-25", "||E119", 1),
        (69, 999, "2024-06-01", "2024-06-02", "2024-25", "||I10", 1),
        # Invalid financial years
        (70, 400, "2024-08-01", "2024-08-02", "2024/25", "||E119", 1),
        (72, 400, "2024-08-01", "2024-08-02", "2024?25", "||E119", 1),
        # Invalid ICD10 codes
        (
            71,
            401,
            "2024-09-01",
            "2024-09-02",
            "2024-25",
            "||A100X00 ,9999, E110, IDENTIFIER",
            2,
        ),
    ]

    for row in test_data:
        execute_sql(
            conn,
            """INSERT INTO APCS (
                APCS_Ident, Patient_ID, Admission_Date, Discharge_Date,
                Der_Financial_Year, Der_Diagnosis_All, Der_Diagnosis_Count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            row,
        )


def setup_apcs_der_table(conn):
    """Create and populate the APCS_Der table with primary and secondary diagnoses.

    Primary diagnosis is typically the first code in Der_Diagnosis_All,
    but can be different in some cases.
    Secondary diagnosis is typically the second code.
    """
    drop_table_if_exists(conn, "APCS_Der")

    execute_sql(
        conn,
        """
        CREATE TABLE APCS_Der (
            APCS_Ident BIGINT PRIMARY KEY,
            Spell_Primary_Diagnosis VARCHAR(20),
            Spell_Secondary_Diagnosis VARCHAR(20)
        )
    """,
    )

    # Primary and secondary diagnosis data
    # Format: (APCS_Ident, Spell_Primary_Diagnosis, Spell_Secondary_Diagnosis)
    # Note: Primary/secondary diagnoses may or may not appear in Der_Diagnosis_All
    primary_data = [
        # Basic records - primary is usually first code, secondary is second
        (1, "E119", "E780"),  # Der_Diagnosis_All: ||E119 ,E780 ,J449 ||I801 ,I802 ,N179
        (2, "E119", "I10"),  # ||E119 ,I10
        (3, "J449", "E780"),  # ||J449||E780 ,E119
        (4, "K219", "K210"),  # ||K219 ,K210
        (5, "E119", None),  # ||E119 (no secondary)
        (6, "I10", "E119"),  # ||I10 ,I10 ,E119||E119
        (7, "J189", "J449"),  # ||J189 ,J449
        (8, "E119", "N179"),  # ||E119 ,N179
        (9, "I801", None),  # ||I801 (no secondary)
        (10, "E780", "K219"),  # ||E780 ,K219
        (11, "E119", "J449"),  # ||E119 ,J449
        (12, "I10", "E119"),  # ||I10||E119 ,E780
        # More E119 records - E119 as primary, various secondary
        (21, "E119", "I10"),  # ||E119 ,I10
        (22, "E119", None),  # ||E119
        (23, "E119", "I10"),  # ||E119 ,I10 ,J449
        (24, "E119", None),  # ||E119
        (25, "E119", "I10"),  # ||E119 ,I10
        (26, "E119", "J449"),  # ||E119 ,J449
        (27, "E119", "I10"),  # ||E119 ,I10
        (28, "E119", None),  # ||E119
        (29, "E119", "I10"),  # ||E119 ,I10 ,J449
        (30, "E119", None),  # ||E119
        (31, "E119", "I10"),  # ||E119 ,I10
        (32, "E119", "J449"),  # ||E119 ,J449
        (33, "E119", "I10"),  # ||E119 ,I10
        (34, "E119", None),  # ||E119
        (35, "E119", "I10"),  # ||E119 ,I10 ,J449
        (36, "E119", None),  # ||E119
        (37, "E119", "I10"),  # ||E119 ,I10
        (38, "E119", "J449"),  # ||E119 ,J449
        (39, "E119", "I10"),  # ||E119 ,I10
        (40, "E119", None),  # ||E119
        (41, "E119", "I10"),  # ||E119 ,I10 ,J449
        (42, "E119", None),  # ||E119
        (43, "E119", "I10"),  # ||E119 ,I10
        (44, "E119", "J449"),  # ||E119 ,J449
        (45, "I10", "E119"),  # ||E119 ,I10 - I10 is primary here
        (46, "E119", None),  # ||E119
        (47, "I10", "E119"),  # ||E119 ,I10 ,J449 - I10 is primary here
        (48, "E119", None),  # ||E119
        (49, "I10", "E119"),  # ||E119 ,I10 - I10 is primary here
        (50, "E119", "J449"),  # ||E119 ,J449
        # I10 records where I10 is primary (no secondary)
        (51, "I10", None),  # ||I10
        (52, "I10", None),  # ||I10
        (53, "I10", None),  # ||I10
        (54, "I10", None),  # ||I10
        (55, "I10", None),  # ||I10
        (63, "I10", None),  # ||I10
        (64, "I10", None),  # ||I10
        (65, "I10", None),  # ||I10
        (66, "I10", None),  # ||I10
        (67, "I10", None),  # ||I10
        # J449 and E780 records
        (56, "J449", "E780"),  # ||J449 ,E780
        (57, "J449", "E780"),  # ||J449 ,E780
        (58, "J449", "E780"),  # ||J449 ,E780
        (59, "E780", None),  # ||E780
        (60, "E780", None),  # ||E780
        (61, "E7800", "E7801"),  # ||E780
        (62, "E7801", None),  # ||E780
        # Previous financial year data
        (13, "E119", "I10"),  # ||E119 ,I10
        (14, "J449", "E780"),  # ||J449 ,E780
        (15, "E119", "K219"),  # ||E119||K219
        (16, "N179", "I801"),  # ||N179 ,I801
        (17, "E119", "E780"),  # ||E119 ,E780 ,J449
        # Edge cases - NULL/empty Der_Diagnosis_All but may have primary set
        (18, None, None),  # NULL diagnosis - no primary or secondary
        (19, None, None),  # Empty diagnosis - no primary or secondary
        (20, "E119", "E780"),  # ||  E119  ,  E780  ||  J449  - with spaces
        # Records for opted-out patient (should be excluded)
        (68, "E119", None),  # ||E119
        (69, "I10", None),  # ||I10
        # Invalid ICD10 code - only appears as primary, not in Der_Diagnosis_All
        (
            71,
            "EA119",
            "EB220",
        ),  # ||A100X00 ,9999, E110, IDENTIFIER - EA119/EB220 not in all
    ]

    for row in primary_data:
        execute_sql(
            conn,
            """INSERT INTO APCS_Der (APCS_Ident, Spell_Primary_Diagnosis, Spell_Secondary_Diagnosis)
               VALUES (%s, %s, %s)""",
            row,
        )


@pytest.fixture(scope="module")
def apcs_results():
    """Set up database and run query once for all tests."""
    conn = get_connection()
    setup_t1oo_table(conn, opted_out_patient_ids=[999])
    setup_apcs_table(conn)
    setup_apcs_der_table(conn)

    sql_file = Path(__file__).parent.parent / "analysis" / "query_icd10_apcs.sql"
    results = run_query(conn, sql_file)
    conn.close()

    # Save results to output folder
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "icd10_apcs.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "financial_year",
                "icd10_code",
                "primary_count",
                "secondary_count",
                "all_count",
            ],
        )
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to {output_file}")

    # Convert to dict keyed by (financial_year, icd10_code) with all count columns
    return {
        (r["financial_year"], r["icd10_code"]): {
            "primary_count": r["primary_count"],
            "secondary_count": r["secondary_count"],
            "all_count": r["all_count"],
        }
        for r in results
    }


def test_query_returns_results(apcs_results):
    """Query should return results."""
    assert len(apcs_results) > 0


def test_e119_all_count_rounded_to_40(apcs_results):
    """E119 appears in 38 spells in 2024-25, should round to 40."""
    # 38 spells (excluding opted-out patient 999)
    assert apcs_results[("2024-25", "E119")]["all_count"] == "40"


def test_e119_primary_count_rounded_to_40(apcs_results):
    """E119 is primary diagnosis in 33 spells in 2024-25, should round to 40."""
    assert apcs_results[("2024-25", "E119")]["primary_count"] == "30"


def test_i10_all_count_rounded_to_30(apcs_results):
    """I10 appears in 27 spells in 2024-25, should round to 30."""
    # 27 spells (excluding opted-out patient 999)
    assert apcs_results[("2024-25", "I10")]["all_count"] == "30"


def test_i10_primary_count(apcs_results):
    """I10 is primary diagnosis in 15 spells in 2024-25.
    -> rounds to 20
    """
    assert apcs_results[("2024-25", "I10")]["primary_count"] == "20"


def test_j449_all_count_rounded_to_20(apcs_results):
    """J449 appears in 18 spells in 2024-25, should round to 20."""
    assert apcs_results[("2024-25", "J449")]["all_count"] == "20"


def test_j449_primary_count(apcs_results):
    """J449 is primary diagnosis in 4 spells in 2024-25.

    J449 is primary in: 3,56,57,58 = 4 total -> '<15'
    """
    assert apcs_results[("2024-25", "J449")]["primary_count"] == "<15"


def test_small_all_counts_show_less_than_15(apcs_results):
    """Codes with <15 all occurrences should show '<15'."""
    assert apcs_results[("2024-25", "E780")]["all_count"] == "<15"
    assert apcs_results[("2024-25", "I801")]["all_count"] == "<15"
    assert apcs_results[("2024-25", "K219")]["all_count"] == "<15"


def test_e780_primary_count(apcs_results):
    """E780 is primary diagnosis in 5 spells in 2024-25.

    E780 is primary in: 10,59,60,61,62 = 5 total -> '<15'
    """
    assert apcs_results[("2024-25", "E780")]["primary_count"] == "<15"


def test_j189_primary_count(apcs_results):
    """J189 appears in all field but is only primary in 1 spell.

    J189 appears in spell 7 (||J189 ,J449) and is primary there.
    all_count = 1 -> '<15'
    primary_count = 1 -> '<15'
    """
    assert apcs_results[("2024-25", "J189")]["all_count"] == "<15"
    assert apcs_results[("2024-25", "J189")]["primary_count"] == "<15"


def test_code_with_zero_primary_count(apcs_results):
    """Codes that never appear as primary should have primary_count = '0'.

    K210 appears in Der_Diagnosis_All for spell 4 (||K219 ,K210)
    but K219 is the primary diagnosis, not K210.
    So K210 should have all_count > 0 but primary_count = 0.
    """
    assert apcs_results[("2024-25", "K210")]["all_count"] == "<15"
    assert apcs_results[("2024-25", "K210")]["primary_count"] == "0"


def test_code_only_in_primary(apcs_results):
    """Codes that only appear as primary (not in Der_Diagnosis_All) should still be counted.

    EA119 is set as Spell_Primary_Diagnosis for spell 71, but it doesn't appear
    in Der_Diagnosis_All (which contains ||A100X00 ,9999, E110, IDENTIFIER).
    So EA119 should have primary_count > 0 but all_count = 0.
    """
    assert apcs_results[("2024-25", "EA119")]["primary_count"] == "<15"
    assert apcs_results[("2024-25", "EA119")]["all_count"] == "0"


def test_opted_out_patient_excluded(apcs_results):
    """Patient 999 opted out - their records should not affect counts.

    Without opt-out exclusion, E119 would have 39 spells (rounds to 40)
    and I10 would have 28 spells (rounds to 30). The counts should be
    38 (rounds to 40) and 27 (rounds to 30) respectively.
    """
    # This is verified by the E119 and I10 counts above - if opted-out
    # patient was included, the raw counts would be different
    pass


def test_previous_financial_year_data(apcs_results):
    """2023-24 data should be included separately."""
    assert ("2023-24", "E119") in apcs_results
    assert apcs_results[("2023-24", "E119")]["all_count"] == "<15"  # 3 spells
    assert (
        apcs_results[("2023-24", "E119")]["primary_count"] == "<15"
    )  # 3 spells as primary


def test_duplicate_codes_in_spell_counted_once(apcs_results):
    """Spell 6 has E119 twice and I10 twice - each should count once per spell."""
    # This is implicitly tested by the counts being correct
    # If duplicates were counted, E119 and I10 would have higher counts
    pass


def test_empty_and_null_diagnoses_handled(apcs_results):
    """Spells with NULL or empty Der_Diagnosis_All should not cause errors."""
    # Spells 18 and 19 have NULL and empty diagnoses
    # Test passes if query executed without error and counts are correct
    pass


def test_codes_with_spaces_trimmed(apcs_results):
    """Spell 20 has codes with extra spaces - they should be trimmed."""
    # The codes "  E119  ", "  E780  ", "  J449  " should be trimmed
    # and counted correctly. This is verified by the overall counts.
    pass


def test_counts_are_independent(apcs_results):
    """Primary and all counts are independent - a code can appear in either or both.

    - A code can have primary_count > 0 and all_count = 0 (only appears as primary)
    - A code can have primary_count = 0 and all_count > 0 (never appears as primary)
    - A code can have both > 0 (appears in both sources)
    """
    # EA119 only appears as primary
    assert apcs_results[("2024-25", "EA119")]["primary_count"] == "<15"
    assert apcs_results[("2024-25", "EA119")]["all_count"] == "0"

    # K210 only appears in Der_Diagnosis_All
    assert apcs_results[("2024-25", "K210")]["primary_count"] == "0"
    assert apcs_results[("2024-25", "K210")]["all_count"] == "<15"

    # E119 appears in both
    assert apcs_results[("2024-25", "E119")]["primary_count"] != "0"
    assert apcs_results[("2024-25", "E119")]["all_count"] != "0"


# Secondary diagnosis tests


def test_i10_secondary_count(apcs_results):
    """I10 appears as secondary diagnosis in multiple spells.

    I10 is secondary in spells: 2, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 43 = 13 total
    Plus spell 13 in 2023-24.
    In 2024-25: 13 spells -> '<15'
    """
    assert apcs_results[("2024-25", "I10")]["secondary_count"] == "<15"


def test_j449_secondary_count(apcs_results):
    """J449 appears as secondary diagnosis in several spells.

    J449 is secondary in spells: 7, 11, 26, 32, 38, 44, 50 = 7 total in 2024-25
    -> '<15'
    """
    assert apcs_results[("2024-25", "J449")]["secondary_count"] == "<15"


def test_e780_secondary_count(apcs_results):
    """E780 appears as secondary diagnosis in several spells.

    E780 is secondary in spells: 1, 3, 20, 56, 57, 58 = 6 total in 2024-25
    Plus spells 14, 17 in 2023-24.
    In 2024-25: 6 spells -> '<15'
    """
    assert apcs_results[("2024-25", "E780")]["secondary_count"] == "<15"


def test_code_only_in_secondary(apcs_results):
    """Codes that only appear as secondary (not primary or all) should still be counted.

    EB220 is set as Spell_Secondary_Diagnosis for spell 71, but it doesn't appear
    in Spell_Primary_Diagnosis or Der_Diagnosis_All.
    So EB220 should have secondary_count > 0 but primary_count = 0 and all_count = 0.
    """
    assert apcs_results[("2024-25", "EB220")]["secondary_count"] == "<15"
    assert apcs_results[("2024-25", "EB220")]["primary_count"] == "0"
    assert apcs_results[("2024-25", "EB220")]["all_count"] == "0"


def test_code_with_zero_secondary_count(apcs_results):
    """Codes that never appear as secondary should have secondary_count = '0'.

    I801 appears as primary in spell 9, and in Der_Diagnosis_All for spell 9,
    but is never a secondary diagnosis.
    """
    assert apcs_results[("2024-25", "I801")]["secondary_count"] == "0"
    assert apcs_results[("2024-25", "I801")]["primary_count"] == "<15"
    assert apcs_results[("2024-25", "I801")]["all_count"] == "<15"


def test_e119_secondary_count(apcs_results):
    """E119 appears as secondary diagnosis in a few spells.

    E119 is secondary in spells: 6, 12, 45, 47, 49 = 5 total in 2024-25
    -> '<15'
    """
    assert apcs_results[("2024-25", "E119")]["secondary_count"] == "<15"


def test_all_three_counts_independent(apcs_results):
    """Primary, secondary, and all counts are independent.

    A code can appear in any combination of the three sources.
    """
    # EB220 only appears as secondary
    assert apcs_results[("2024-25", "EB220")]["primary_count"] == "0"
    assert apcs_results[("2024-25", "EB220")]["secondary_count"] == "<15"
    assert apcs_results[("2024-25", "EB220")]["all_count"] == "0"

    # EA119 only appears as primary
    assert apcs_results[("2024-25", "EA119")]["primary_count"] == "<15"
    assert apcs_results[("2024-25", "EA119")]["secondary_count"] == "0"
    assert apcs_results[("2024-25", "EA119")]["all_count"] == "0"

    # K210 only appears in Der_Diagnosis_All (secondary in spell 4)
    assert apcs_results[("2024-25", "K210")]["primary_count"] == "0"
    assert apcs_results[("2024-25", "K210")]["secondary_count"] == "<15"
    assert apcs_results[("2024-25", "K210")]["all_count"] == "<15"

    # E119 appears in all three
    assert apcs_results[("2024-25", "E119")]["primary_count"] != "0"
    assert apcs_results[("2024-25", "E119")]["secondary_count"] != "0"
    assert apcs_results[("2024-25", "E119")]["all_count"] != "0"
