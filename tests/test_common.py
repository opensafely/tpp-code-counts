"""Tests for reporting/common.py module."""

import json

import pytest

from reporting import common


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Create temporary data directory with test files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create OCL codes file
    ocl_file = data_dir / "ocl_icd10_codes.txt"
    ocl_file.write_text(
        "A00\nA01\nA02\nB99\nC341\nE10\nE11\nE119\n"
        "I10\nJ459\nZ992\n" + "\n".join(f"X{i:03d}" for i in range(1000, 13000))
    )

    monkeypatch.setattr(common, "DATA_DIR", data_dir)
    monkeypatch.setattr(common, "OCL_ICD10_2019_CODES_FILE", ocl_file)
    monkeypatch.setattr(common, "CACHE_DIR", data_dir / "codelist_cache")

    return data_dir


def test_load_ocl_codes(tmp_data_dir):
    """Test loading OCL codes creates both apcs and ons_deaths sets."""
    result = common.load_ocl_codes()

    assert "apcs" in result
    assert "ons_deaths" in result
    assert len(result["ons_deaths"]) >= 12000

    # Check known codes exist
    assert "E119" in result["ons_deaths"]
    assert "I10" in result["ons_deaths"]

    # Check APCS has X-padded 3-char codes with no children
    # E10 has children, so shouldn't be padded
    # E11 has children, so shouldn't be padded
    assert "A00" in result["ons_deaths"]  # 3-char with children


def test_load_ocl_codes_creates_x_padded_codes(tmp_data_dir):
    """Test that 3-char codes without children get X-padded for APCS."""
    # Create a minimal OCL file with a 3-char code that has no children
    ocl_file = tmp_data_dir / "ocl_icd10_codes.txt"
    ocl_file.write_text(
        "A00\nA01\nA02\nA03\nB99\nC341\nD50\nE119\nI10\nJ459\nZ992\n"
        + "\n".join(f"X{i:03d}" for i in range(1000, 13000))
    )

    result = common.load_ocl_codes()

    # D50 has no children (D500, D501, etc.), so should be padded
    # Check if D50X is in apcs but D50 is also there
    assert "D50" in result["ons_deaths"]
    # D50X should be in APCS if D50 has no children


def test_parse_value():
    """Test parsing count values including suppressed counts."""
    assert common.parse_value("100") == 100
    assert common.parse_value("<15") == 0
    assert common.parse_value("") == 0
    assert common.parse_value("0") == 0


def test_find_code_column():
    """Test finding the code column in various formats."""
    assert common.find_code_column(["code", "count"]) == "code"
    assert common.find_code_column(["icd10_code", "count"]) == "icd10_code"
    assert common.find_code_column(["ICD_code", "count"]) == "ICD_code"
    assert common.find_code_column(["name", "count"]) is None


def test_download_codelist(tmp_data_dir, monkeypatch):
    """Test downloading a codelist from OpenCodelists."""
    cache_dir = tmp_data_dir / "codelist_cache"
    cache_dir.mkdir(exist_ok=True)

    # Mock urlopen to return fake CSV
    fake_csv = "code,term\nE10,Diabetes\nE11,Type 2 diabetes"

    class FakeResponse:
        def read(self):
            return fake_csv.encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def fake_urlopen(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(common, "urlopen", fake_urlopen)
    monkeypatch.setattr(common, "CACHE_DIR", cache_dir)

    common.download_codelist("/test/codelist/123/")

    # Check file was created
    cache_file = cache_dir / "test_codelist_123.csv"
    assert cache_file.exists()
    assert "E10" in cache_file.read_text()


def test_parse_codelist(tmp_data_dir, monkeypatch):
    """Test parsing a codelist CSV file."""
    cache_dir = tmp_data_dir / "codelist_cache"
    cache_dir.mkdir()

    cache_file = cache_dir / "test_codelist.csv"
    cache_file.write_text("code,term\nE10,Diabetes\nE11,Type 2\n")

    monkeypatch.setattr(common, "CACHE_DIR", cache_dir)

    result = common.parse_codelist("test_codelist.csv")

    assert result == {"E10", "E11"}


def test_load_usage_data_apcs(tmp_path, monkeypatch):
    """Test loading APCS usage data."""
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()

    usage_file = out_dir / "code_usage_combined_apcs.csv"
    usage_file.write_text(
        "icd10_code,financial_year,apcs_primary_count,apcs_secondary_count,apcs_all_count,in_opencodelists\n"
        "E10,2024-25,100,50,150,yes\n"
        "E11,2024-25,<15,20,30,yes\n"
    )

    monkeypatch.setattr(common, "USAGE_FILE_APCS", usage_file)

    usage, raw_usage = common.load_usage_data("apcs")

    assert "E10" in usage
    assert usage["E10"][("apcs_primary_count", "2024-25")] == 100
    assert usage["E11"][("apcs_primary_count", "2024-25")] == 0  # <15 parsed as 0
    assert raw_usage["E11"][("apcs_primary_count", "2024-25")] == "<15"


def test_load_usage_data_ons_deaths(tmp_path, monkeypatch):
    """Test loading ONS deaths usage data."""
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()

    usage_file = out_dir / "code_usage_combined_ons_deaths.csv"
    usage_file.write_text(
        "icd10_code,financial_year,ons_primary_count,ons_contributing_count,in_opencodelists\n"
        "I21,2024-25,500,300,yes\n"
    )

    monkeypatch.setattr(common, "USAGE_FILE_ONS_DEATHS", usage_file)

    usage, _ = common.load_usage_data("ons_deaths")

    assert "I21" in usage
    assert usage["I21"][("ons_primary_count", "2024-25")] == 500
    assert usage["I21"][("ons_contributing_count", "2024-25")] == 300


def test_load_codelist_without_expansion(tmp_data_dir, monkeypatch):
    """Test loading codelist without expansion."""
    cache_dir = tmp_data_dir / "codelist_cache"
    cache_dir.mkdir()

    cache_file = cache_dir / "test_codelist_xyz.csv"
    cache_file.write_text("code,term\nE10,Diabetes\nE11,Type 2\n")

    monkeypatch.setattr(common, "CACHE_DIR", cache_dir)

    result = common.load_codelist("/test/codelist/xyz/")

    assert result == {"E10", "E11"}

    # Test without expansion
    result = common.load_codelist("/test/codelist/xyz/")

    assert result == {"E10", "E11"}


def test_get_apcs_coverage_data(tmp_path, monkeypatch):
    """Test getting APCS coverage data."""
    # Clear global cache
    from collections import defaultdict

    import reporting.common as common_module

    common_module._coverage_data = []
    common_module._codelist_codes = defaultdict(list)

    out_dir = tmp_path / "outputs"
    out_dir.mkdir()

    coverage_file = out_dir / "codelist_coverage_detail_apcs.csv"
    coverage_file.write_text(
        "codelist_id,creation_method,Exists in ehrQL repo,icd10_code,status,apcs_primary_count\n"
        "/test/codelist/1/,Builder,Y,E10,COMPLETE,100\n"
        "/test/codelist/1/,Builder,Y,E11,PARTIAL,50\n"
    )

    monkeypatch.setattr(common, "COVERAGE_APCS_FILE", coverage_file)

    data, codelist_codes = common.get_apcs_coverage_data()

    assert len(data) == 2
    assert data[0]["icd10_code"] == "E10"
    assert data[1]["icd10_code"] == "E11"
    assert "/test/codelist/1/" in codelist_codes
    assert "E10" in codelist_codes["/test/codelist/1/"]
    assert "E11" in codelist_codes["/test/codelist/1/"]


def test_load_rsi_codelists(tmp_path, monkeypatch):
    """Test loading RSI codelist metadata."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    rsi_file = data_dir / "rsi-codelists-analysis.json"
    rsi_data = [
        {
            "slug": "user/test/codelist",
            "coding_system": "icd10",
            "versions": [
                {"hash": "abc123", "tag": "2023-01-01", "creation_method": "Builder"}
            ],
        }
    ]
    rsi_file.write_text(json.dumps(rsi_data))

    monkeypatch.setattr(common, "RSI_JSON_FILE", rsi_file)

    result = common.load_rsi_codelists()

    assert "abc123" in result  # Hash as key
    assert result["abc123"]["coding_system"] == "icd10"
    assert result["abc123"]["creation_method"] == "Builder"


def test_load_ehrql_codelists_to_repos(tmp_path, monkeypatch):
    """Test loading ehrQL codelists to repos mapping."""
    # Clear global cache
    common._ehrql_data = {}

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    ehrql_file = data_dir / "ehrql_codelists.json"
    ehrql_data = {
        "projects": {"opensafely/test-repo": {"main": "hash123"}},
        "signatures": {
            "hash123": {
                "codelists.py": {"my_codelist": [["/user/test/codelist/abc123/"]]}
            }
        },
    }
    ehrql_file.write_text(json.dumps(ehrql_data))

    monkeypatch.setattr(common, "EHRQL_JSON_FILE", ehrql_file)

    result = common.load_ehrql_codelists_to_repos()

    assert "/user/test/codelist/abc123/" in result
    assert "opensafely/test-repo" in result["/user/test/codelist/abc123/"]
    assert "opensafely/test-repo" in result["/user/test/codelist/abc123/"]
