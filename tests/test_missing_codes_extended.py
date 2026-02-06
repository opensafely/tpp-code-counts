"""Extended tests for missing_codes.py to reach 90%+ coverage."""

import csv
import io
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from reporting import missing_codes


@pytest.fixture
def mock_extended_missing_codes_data(tmp_path, monkeypatch):
    """Create extended mock data for missing_codes tests."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "outputs"
    cache_dir = data_dir / "codelist_cache"

    data_dir.mkdir()
    out_dir.mkdir()
    cache_dir.mkdir()

    # Create OCL codes file
    ocl_file = data_dir / "icd10-2019-refset-full.txt"
    ocl_file.write_text("A00\nA000\nE10\nE100\nE101\nI10\n")

    # Create usage file with various scenarios
    usage_file = out_dir / "code_usage_combined_apcs.csv"
    usage_file.write_text(
        "icd10_code,financial_year,apcs_primary_count,apcs_secondary_count,apcs_all_count,in_opencodelists\n"
        "A00,2024-25,100,50,150,yes\n"
        "A000,2024-25,80,40,120,yes\n"
        "E10,2024-25,1000,500,1500,yes\n"
        "E100,2024-25,200,100,300,no\n"
        "E101,2024-25,150,75,225,yes\n"
        "I10,2024-25,500,250,750,yes\n"
        "Z99,2024-25,50,25,75,no\n"
    )

    monkeypatch.setattr(missing_codes, "DATA_DIR", data_dir)
    monkeypatch.setattr(missing_codes, "OUT_DIR", out_dir)
    monkeypatch.setattr(missing_codes, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(missing_codes, "OCL_ICD10_2019_CODES_FILE", ocl_file)
    monkeypatch.setattr(missing_codes, "USAGE_FILE_APCS", usage_file)

    return {"data_dir": data_dir, "out_dir": out_dir, "cache_dir": cache_dir}


def test_deduplicate_files_multiple_versions():
    """Test deduplicating when multiple versions exist."""
    files = [
        "output/icd10_apcs_2023_24_rows_100_200.csv",
        "output/icd10_apcs_2023_24_rows_100_300.csv",  # Same prefix, higher second number
        "output/icd10_apcs_2024_25_rows_200_400.csv",
        "output/opcs4_apcs_2023_24_rows_10_20.csv",
    ]

    result = missing_codes.deduplicate_files(files)

    # Should keep 3 files: one icd10_2023_24 (the 300 one), one icd10_2024_25, one opcs4
    assert len(result) == 3
    # Should have the 300 version, not the 200 version
    matching = [f for f in result if "2023_24" in f and "icd10" in f]
    assert len(matching) == 1
    assert "rows_100_300" in matching[0]


def test_get_file_key():
    """Test extracting file key from name."""
    key = missing_codes.get_file_key("output/icd10_apcs_2023_24_rows_9983_13591.csv")
    assert key == "output/icd10_apcs_2023_24_rows_9983"

    key = missing_codes.get_file_key("output/opcs4_apcs_2024_25.csv")
    assert key == "output/opcs4_apcs_2024_25"


def test_fy_from_filename():
    """Test extracting financial year from filename."""
    fy = missing_codes.fy_from_filename("icd10_apcs_2023_24.csv")
    assert fy == "2023-24"

    fy = missing_codes.fy_from_filename("data_2024_25.csv")
    assert fy == "2024-25"


def test_process_csv_populates_usage():
    """Test process_csv populates usage dict."""
    from collections import defaultdict

    csv_data = "icd10_code,primary_count,secondary_count,all_count\nA00,100,50,150\n"
    reader = csv.DictReader(io.StringIO(csv_data))

    # Create proper nested defaultdict structure
    usage = {
        "apcs": defaultdict(lambda: defaultdict(dict)),
        "ons_deaths": defaultdict(lambda: defaultdict(dict)),
    }

    missing_codes.process_csv(reader, "icd10_apcs_2023_24.csv", usage)

    # Check data was populated
    assert usage["apcs"]["A00"]["2023-24"]["apcs_all_count"] == "150"


def test_process_csv_handles_ons_deaths():
    """Test process_csv handles ONS deaths files."""
    from collections import defaultdict

    csv_data = "icd10_code,primary_cause_count,contributing_cause_count\nE10,200,100\n"
    reader = csv.DictReader(io.StringIO(csv_data))

    usage = {
        "apcs": defaultdict(lambda: defaultdict(dict)),
        "ons_deaths": defaultdict(lambda: defaultdict(dict)),
    }

    missing_codes.process_csv(reader, "icd10_ons_deaths_2024_25.csv", usage)

    # Check ONS data was populated
    assert usage["ons_deaths"]["E10"]["2024-25"]["ons_primary_count"] == "200"
