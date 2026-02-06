"""Tests for reporting/analyze_prefix_matching.py module."""

import csv
import json

import pytest

from reporting import analyze_prefix_matching as apm
from reporting import common


@pytest.fixture
def mock_prefix_matching_data(tmp_path, monkeypatch):
    """Create mock data files for prefix matching tests."""
    # Clear global caches
    from collections import defaultdict

    import reporting.common as common_module

    common_module._coverage_data = []
    common_module._codelist_codes = defaultdict(list)

    data_dir = tmp_path / "data"
    out_dir = tmp_path / "outputs"

    data_dir.mkdir()
    out_dir.mkdir()

    # Create coverage detail file
    coverage_file = out_dir / "codelist_coverage_detail_apcs.csv"
    coverage_file.write_text(
        "codelist_id,creation_method,Exists in ehrQL repo,icd10_code,status,apcs_primary_count,apcs_secondary_count,apcs_all_count\n"
        "/test/codelist/1/,Builder,Y,E10,COMPLETE,100,50,150\n"
        "/test/codelist/1/,Builder,Y,E100,EXTRA,30,20,50\n"
        "/test/codelist/1/,Builder,Y,E101,EXTRA,20,<15,30\n"
        "/test/codelist/2/,Builder,Y,M60,NONE,0,0,0\n"
        "/test/codelist/2/,Builder,Y,M600,EXTRA,50,30,80\n"
        "/test/codelist/2/,Builder,Y,M601,EXTRA,<15,<15,20\n"
    )

    # Create ehrQL codelists file
    ehrql_file = data_dir / "ehrql_codelists.json"
    ehrql_data = {
        "repo_to_codelists": {
            "opensafely/test-repo": ["/test/codelist/1/", "/test/codelist/2/"]
        }
    }
    ehrql_file.write_text(json.dumps(ehrql_data))

    monkeypatch.setattr(common, "DATA_DIR", data_dir)
    monkeypatch.setattr(common, "OUT_DIR", out_dir)
    monkeypatch.setattr(common, "COVERAGE_APCS_FILE", coverage_file)
    monkeypatch.setattr(common, "EHRQL_JSON_FILE", ehrql_file)
    monkeypatch.setattr(apm, "OUTPUT_CSV", out_dir / "prefix_matching_analysis.csv")
    monkeypatch.setattr(apm, "OUTPUT_MD", out_dir / "prefix_matching_analysis.md")
    monkeypatch.setattr(apm, "REPOS_OUTPUT_FILE", out_dir / "prefix_matching_repos.csv")

    return {
        "data_dir": data_dir,
        "out_dir": out_dir,
    }


def test_parse_count():
    """Test parsing count values."""
    assert apm.parse_count("100") == 100
    assert apm.parse_count("<15") == 0
    assert apm.parse_count("") == 0
    assert apm.parse_count("0") == 0


def test_is_descendant():
    """Test checking if a code is a descendant of another."""
    assert apm.is_descendant("E100", "E10") is True
    assert apm.is_descendant("E101", "E10") is True
    assert apm.is_descendant("E10", "E10") is False
    assert apm.is_descendant("E11", "E10") is False
    assert apm.is_descendant("E1", "E10") is False


def test_get_codelist_codes(mock_prefix_matching_data):
    """Test getting all rows for a specific codelist."""
    data, _ = common.get_apcs_coverage_data()

    rows = apm.get_codelist_codes(data, "/test/codelist/1/")

    # _coverage_data includes all rows (COMPLETE, EXTRA, etc.)
    assert len(rows) == 3
    assert any(r["icd10_code"] == "E10" for r in rows)
    assert any(r["icd10_code"] == "E100" for r in rows)


def test_analyze_primary_secondary(mock_prefix_matching_data):
    """Test analyzing primary and secondary counts."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/codelist/1/"]

    result = apm.analyze_primary_secondary(codelist_rows)

    assert "baseline_primary" in result
    assert "strict_primary" in result
    assert "partial_primary" in result
    assert "baseline_secondary" in result
    assert "strict_secondary" in result
    assert "partial_secondary" in result

    # Baseline should be 100 (only E10 which is COMPLETE)
    assert result["baseline_primary"] == 100
    # Strict should include EXTRA descendants of COMPLETE codes
    assert result["strict_primary"] >= 100
    # Partial should include EXTRA descendants of COMPLETE and PARTIAL codes
    assert result["partial_primary"] >= result["strict_primary"]


def test_analyze_none_uploaded(mock_prefix_matching_data):
    """Test analyzing NONE codes for uploaded codelists."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/codelist/2/"]

    result = apm.analyze_none_uploaded(codelist_rows)

    assert "none_primary" in result
    assert "none_secondary" in result

    # M60 is NONE with EXTRA descendants M600 (50), M601 (<15 = 0)
    # Should count their usage
    assert result["none_primary"] == 50  # M600's primary count


def test_analyze_all_count(mock_prefix_matching_data):
    """Test analyzing all_count field."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/codelist/1/"]

    result = apm.analyze_all_count(codelist_rows)

    assert "baseline_all" in result
    assert "with_partial_children_all" in result

    # Baseline should be 150 (E10's all_count)
    assert result["baseline_all"] == 150


def test_run_analysis_creates_output_files(mock_prefix_matching_data):
    """Test that run_analysis creates expected output files."""
    results = apm.run_analysis()

    assert isinstance(results, list)
    assert len(results) > 0

    # Check CSV was created
    csv_file = mock_prefix_matching_data["out_dir"] / "prefix_matching_analysis.csv"
    assert csv_file.exists()

    with open(csv_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) > 0
        assert reader.fieldnames
        assert "codelist_id" in reader.fieldnames
        assert "baseline_primary" in reader.fieldnames


def test_load_prefix_matching_results(mock_prefix_matching_data):
    """Test loading prefix matching results."""
    # First run analysis to create the CSV
    apm.run_analysis()

    # Then load the results
    discrepancies = apm.load_prefix_matching_results()

    assert isinstance(discrepancies, list)
    # Should have discrepancies for codelists with EXTRA descendants
    assert len(discrepancies) > 0

    # Check structure
    if discrepancies:
        disc = discrepancies[0]
        assert "codelist_id" in disc
        assert "baseline_primary" in disc
        assert "with_x_padding" in disc
        assert "with_prefix_matching" in disc


def test_map_to_repos_creates_output(mock_prefix_matching_data):
    """Test that map_to_repos creates expected output."""
    # First run analysis
    apm.run_analysis()

    # Then map to repos
    apm.map_to_repos()

    repos_file = mock_prefix_matching_data["out_dir"] / "prefix_matching_repos.csv"
    assert repos_file.exists()

    with open(repos_file) as f:
        reader = csv.DictReader(f)

        assert reader.fieldnames
        assert "repo" in reader.fieldnames
        assert "codelist" in reader.fieldnames
        assert "current_event_count" in reader.fieldnames
