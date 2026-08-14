"""Tests for reporting/analyze_codelist_coverage.py module."""

import csv
import json

import pytest

from reporting import analyze_codelist_coverage as acc
from reporting import common


@pytest.fixture
def mock_data_files(tmp_path, monkeypatch):
    """Create mock data files for testing."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "outputs"
    cache_dir = data_dir / "codelist_cache"

    data_dir.mkdir()
    out_dir.mkdir()
    cache_dir.mkdir()

    # Create OCL codes file with proper name
    ocl_file = data_dir / "icd10-2019-refset-full.txt"
    codes = [
        "A00",
        "A000",
        "A001",
        "A009",
        "B99",
        "B990",
        "B991",
        "C341",
        "E10",
        "E100",
        "E101",
        "E109",
        "E11",
        "E110",
        "E111",
        "E119",
        "I10",
        "J459",
        "M33",
        "M330",
        "M331",
        "M332",
        "M339",
        "M60",
        "M600",
        "M601",
        "M602",
        "M608",
        "M609",
        "Z992",
    ]
    codes.extend([f"X{i:03d}" for i in range(1000, 13000)])
    ocl_file.write_text("\n".join(codes))

    # Create usage files
    usage_apcs = out_dir / "code_usage_combined_apcs.csv"
    usage_apcs.write_text(
        "icd10_code,financial_year,apcs_primary_count,apcs_secondary_count,apcs_all_count,in_opencodelists\n"
        "E100,2024-25,100,50,150,yes\n"
        "E101,2024-25,80,40,120,yes\n"
        "M600,2024-25,30,20,50,yes\n"
        "M601,2024-25,<15,<15,20,yes\n"
    )

    usage_ons = out_dir / "code_usage_combined_ons_deaths.csv"
    usage_ons.write_text(
        "icd10_code,financial_year,ons_primary_count,ons_contributing_count,in_opencodelists\n"
        "E100,2024-25,50,30,yes\n"
    )

    # Create ehrql codelists file
    ehrql_file = data_dir / "ehrql_codelists.json"
    ehrql_data = {
        "signatures": {"hash1": {"file.py": {"var1": [["/test/codelist/1/", []]]}}}
    }
    ehrql_file.write_text(json.dumps(ehrql_data))

    # Create RSI codelists file
    rsi_file = data_dir / "rsi-codelists-analysis.json"
    rsi_data = {
        "codelists": [
            {
                "full_slug": "test/codelist",
                "coding_system": "icd10",
                "versions": [
                    {
                        "hash": "abc123",
                        "full_slug": "test/codelist/abc123",
                        "creation_method": "Builder",
                    }
                ],
            }
        ]
    }
    rsi_file.write_text(json.dumps(rsi_data))

    # Create a test codelist
    test_codelist = cache_dir / "test_codelist_1.csv"
    test_codelist.write_text("code,term\nE10,Diabetes\n")

    monkeypatch.setattr(common, "DATA_DIR", data_dir)
    monkeypatch.setattr(common, "OUT_DIR", out_dir)
    monkeypatch.setattr(common, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(common, "OCL_ICD10_2019_CODES_FILE", ocl_file)
    monkeypatch.setattr(common, "USAGE_FILE_APCS", usage_apcs)
    monkeypatch.setattr(common, "USAGE_FILE_ONS_DEATHS", usage_ons)
    monkeypatch.setattr(common, "EHRQL_JSON_FILE", ehrql_file)
    monkeypatch.setattr(common, "RSI_JSON_FILE", rsi_file)
    monkeypatch.setattr(
        common, "COVERAGE_APCS_FILE", out_dir / "codelist_coverage_detail_apcs.csv"
    )
    monkeypatch.setattr(
        common,
        "COVERAGE_ONS_DEATHS_FILE",
        out_dir / "codelist_coverage_detail_ons_deaths.csv",
    )

    return {
        "data_dir": data_dir,
        "out_dir": out_dir,
        "cache_dir": cache_dir,
    }


def test_get_descendants():
    """Test getting descendants of a code."""
    all_codes = {"E10", "E100", "E101", "E109", "E11"}

    descendants = acc.get_descendants("E10", all_codes)

    assert "E100" in descendants
    assert "E101" in descendants
    assert "E109" in descendants
    assert "E10" not in descendants
    assert "E11" not in descendants


def test_get_descendants_no_children():
    """Test getting descendants when code has no children."""
    all_codes = {"E119", "I10"}

    descendants = acc.get_descendants("E119", all_codes)

    assert len(descendants) == 0


def test_classify_code_descendants_complete():
    """Test classifying a code as COMPLETE."""
    codelist_codes = {"E10", "E100", "E101", "E109"}
    hierarchy_codes = {"E10", "E100", "E101", "E109"}

    result = acc.classify_code_descendants("E10", codelist_codes, hierarchy_codes)

    assert result == "COMPLETE"


def test_classify_code_descendants_partial():
    """Test classifying a code as PARTIAL."""
    codelist_codes = {"E10", "E100"}  # Missing E101, E109
    hierarchy_codes = {"E10", "E100", "E101", "E109"}

    result = acc.classify_code_descendants("E10", codelist_codes, hierarchy_codes)

    assert result == "PARTIAL"


def test_classify_code_descendants_none():
    """Test classifying a code as NONE."""
    codelist_codes = {"E10"}  # No descendants in codelist
    hierarchy_codes = {"E10", "E100", "E101", "E109"}

    result = acc.classify_code_descendants("E10", codelist_codes, hierarchy_codes)

    assert result == "NONE"


def test_classify_code_descendants_four_char_always_complete():
    """Test that 4-character codes are always COMPLETE."""
    codelist_codes = {"E119"}
    hierarchy_codes = {"E119"}

    result = acc.classify_code_descendants("E119", codelist_codes, hierarchy_codes)

    assert result == "COMPLETE"


def test_analyze_codelist(mock_data_files):
    """Test analyzing a single codelist."""
    ocl_codes = common.load_ocl_codes()
    usage_data, _ = common.load_usage_data("apcs")
    usage_codes = set(usage_data.keys())

    # Codelist has E10 only
    codelist_codes = {"E10"}

    result = acc.analyze_codelist(
        "/test/codelist/1/",
        codelist_codes,
        ocl_codes["apcs"],
        usage_codes,
        usage_data,
        "Builder",
        ocl_codes["ons_deaths"],
        from_ehrql=True,
    )

    assert result["codelist_id"] == "/test/codelist/1/"
    assert result["creation_method"] == "Builder"
    assert result["from_ehrql"] is True
    assert "code_classifications" in result

    # E10 should be PARTIAL or NONE (depending on whether E109 exists in OCL)
    assert "E10" in result["code_classifications"]
    # E100 and E101 are not in the codelist, so they won't be classified
    assert "E100" not in result["code_classifications"]
    assert "E101" not in result["code_classifications"]


def test_write_csv_report(mock_data_files, tmp_path):
    """Test writing CSV report."""
    ocl_codes = common.load_ocl_codes()
    usage_data, raw_usage = common.load_usage_data("apcs")

    results = [
        {
            "codelist_id": "/test/codelist/1/",
            "creation_method": "Builder",
            "from_ehrql": True,
            "total_codes": 2,
            "codelist_codes": {"E10", "E100"},
            "code_classifications": {"E10": "PARTIAL", "E100": "EXTRA"},
            "actual_usage": {},
            "missing_descendants": [],
            "potential_usage": {},
        }
    ]

    output_file = tmp_path / "test_coverage.csv"

    acc.write_csv_report(
        results,
        usage_data,
        raw_usage,
        output_file,
        "apcs",
        ocl_codes["ons_deaths"],
    )

    assert output_file.exists()

    with open(output_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        assert len(rows) >= 2
        assert any(row["icd10_code"] == "E10" for row in rows)
        assert any(row["icd10_code"] == "E100" for row in rows)


def test_write_csv_report_restricts_only_extra_codes(mock_data_files, tmp_path):
    """The allowlist filters prefix descendants without filtering baseline codes."""
    ocl_codes = common.load_ocl_codes()
    usage_data, raw_usage = common.load_usage_data("apcs")
    usage_data["E10X"] = {("apcs_primary_count", "2024-25"): 25}
    raw_usage["E10X"] = {("apcs_primary_count", "2024-25"): "25"}
    results = [
        {
            "codelist_id": "/test/codelist/1/",
            "creation_method": "Builder",
            "from_ehrql": True,
            "codelist_codes": {"E10"},
            "code_classifications": {"E10": "COMPLETE"},
        }
    ]
    output_file = tmp_path / "restricted_coverage.csv"

    acc.write_csv_report(
        results,
        usage_data,
        raw_usage,
        output_file,
        "apcs",
        ocl_codes["ons_deaths"],
        allowed_extra_codes={"E100"},
    )

    with open(output_file) as f:
        rows = list(csv.DictReader(f))

    assert {row["icd10_code"] for row in rows} == {"E10", "E100", "E10X"}
    assert (
        next(row for row in rows if row["icd10_code"] == "E10")["status"] == "COMPLETE"
    )
    assert next(row for row in rows if row["icd10_code"] == "E100")["status"] == "EXTRA"
    assert next(row for row in rows if row["icd10_code"] == "E10X")["status"] == "EXTRA"


def test_analyze_codelist_restricts_missing_descendants():
    usage_data = {
        "E100": {("apcs_primary_count", "2024-25"): 10},
        "E101": {("apcs_primary_count", "2024-25"): 20},
        "E10X": {("apcs_primary_count", "2024-25"): 30},
    }

    result = acc.analyze_codelist(
        "test",
        {"E10"},
        {"E10"},
        set(usage_data),
        usage_data,
        "Builder",
        {"E10"},
        allowed_extra_codes={"E100"},
    )

    assert result["missing_descendants"] == ["E100", "E10X"]
    assert result["potential_usage"] == {("apcs_primary_count", "2024-25"): 40}


def test_load_allowed_prefix_codes(tmp_path, monkeypatch):
    allowlist = tmp_path / "allowed.txt"
    allowlist.write_text("M100\n\nM101\n")
    monkeypatch.setattr(acc, "ALLOWED_PREFIX_CODES_FILE", allowlist)

    assert acc.load_allowed_prefix_codes() == {"M100", "M101"}


def test_restriction_flag_is_opt_in():
    assert acc.parse_args([]).restrict_prefix_matching_codes is False
    assert (
        acc.parse_args(
            ["--restrict-prefix-matching-codes"]
        ).restrict_prefix_matching_codes
        is True
    )


def test_format_number():
    """Test formatting numbers with thousands separator."""
    assert acc.format_number(1000) == "1,000"
    assert acc.format_number(1000000) == "1,000,000"
    assert acc.format_number(100) == "100"
