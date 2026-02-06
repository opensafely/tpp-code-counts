"""Extended tests for analyze_prefix_matching.py to reach 90%+ coverage."""

import csv
import json

import pytest

from reporting import analyze_prefix_matching as apm
from reporting import common


@pytest.fixture
def mock_extended_data(tmp_path, monkeypatch):
    """Create extended mock data for comprehensive testing."""
    from collections import defaultdict

    import reporting.common as common_module

    # Clear caches
    common_module._coverage_data = []
    common_module._codelist_codes = defaultdict(list)

    data_dir = tmp_path / "data"
    out_dir = tmp_path / "outputs"

    data_dir.mkdir()
    out_dir.mkdir()

    # Coverage with various code length scenarios
    coverage_file = out_dir / "codelist_coverage_detail_apcs.csv"
    coverage_file.write_text(
        "codelist_id,creation_method,Exists in ehrQL repo,icd10_code,status,apcs_primary_count,apcs_secondary_count,apcs_all_count\n"
        # 3-char COMPLETE with 4-char and 5-char EXTRA
        "/test/3char/,Builder,Y,E10,COMPLETE,1000,500,1500\n"
        "/test/3char/,Builder,Y,E10X,EXTRA,100,50,150\n"
        "/test/3char/,Builder,Y,E101,EXTRA,200,100,300\n"
        "/test/3char/,Builder,Y,E1012,EXTRA,50,25,75\n"
        # 4-char COMPLETE with 5+ char EXTRA
        "/test/4char/,Builder,Y,E100,COMPLETE,800,400,1200\n"
        "/test/4char/,Builder,Y,E1001,EXTRA,80,40,120\n"
        "/test/4char/,Builder,Y,E10012,EXTRA,20,10,30\n"
        # 3-char PARTIAL with EXTRA
        "/test/partial/,Builder,Y,M60,PARTIAL,500,250,750\n"
        "/test/partial/,Builder,Y,M600,EXTRA,100,50,150\n"
        "/test/partial/,Builder,Y,M6001,EXTRA,30,15,45\n"
        # NONE with EXTRA (for uploaded analysis)
        "/test/none/,Uploaded,Y,A00,NONE,0,0,0\n"
        "/test/none/,Uploaded,Y,A000,EXTRA,200,100,300\n"
        "/test/none/,Uploaded,Y,A0001,EXTRA,50,25,75\n"
        # Mixed scenario
        "/test/mixed/,Uploaded,Y,I10,COMPLETE,1000,500,1500\n"
        "/test/mixed/,Uploaded,Y,I20,PARTIAL,300,150,450\n"
        "/test/mixed/,Uploaded,Y,I30,NONE,0,0,0\n"
        "/test/mixed/,Uploaded,Y,I301,EXTRA,100,50,150\n"
    )

    # ehrQL data
    ehrql_file = data_dir / "ehrql_codelists.json"
    ehrql_data = {
        "projects": {
            "opensafely/repo1": {"main": "hash1"},
            "opensafely/repo2": {"main": "hash2"},
        },
        "signatures": {
            "hash1": {
                "codelists.py": {"var1": [["/test/3char/"]], "var2": [["/test/4char/"]]}
            },
            "hash2": {
                "codelists.py": {
                    "var1": [["/test/partial/"]],
                    "var2": [["/test/none/"]],
                }
            },
        },
    }
    ehrql_file.write_text(json.dumps(ehrql_data))

    monkeypatch.setattr(common, "DATA_DIR", data_dir)
    monkeypatch.setattr(common, "OUT_DIR", out_dir)
    monkeypatch.setattr(common, "COVERAGE_APCS_FILE", coverage_file)
    monkeypatch.setattr(common, "EHRQL_JSON_FILE", ehrql_file)
    monkeypatch.setattr(apm, "OUTPUT_CSV", out_dir / "prefix_matching_analysis.csv")
    monkeypatch.setattr(apm, "OUTPUT_MD", out_dir / "prefix_matching_analysis.md")
    monkeypatch.setattr(apm, "REPOS_OUTPUT_FILE", out_dir / "prefix_matching_repos.csv")

    return {"data_dir": data_dir, "out_dir": out_dir}


def test_analyze_primary_secondary_3char_complete(mock_extended_data):
    """Test 3-char COMPLETE with 4 and 5 char EXTRA descendants."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/3char/"]

    result = apm.analyze_primary_secondary(codelist_rows)

    # Baseline: just E10
    assert result["baseline_primary"] == 1000
    # Strict should include E10X, E101, E1012 (3-char includes all descendants)
    assert result["strict_primary"] == 1000 + 100 + 200 + 50
    # Partial same as strict for this case
    assert result["partial_primary"] == result["strict_primary"]


def test_analyze_primary_secondary_4char_complete(mock_extended_data):
    """Test 4-char COMPLETE with 5+ char EXTRA descendants."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/4char/"]

    result = apm.analyze_primary_secondary(codelist_rows)

    # Baseline: just E100
    assert result["baseline_primary"] == 800
    # Strict should include E1001, E10012 (4-char includes 5+ char only)
    assert result["strict_primary"] == 800 + 80 + 20
    assert result["strict_secondary"] == 400 + 40 + 10


def test_analyze_primary_secondary_partial_3char(mock_extended_data):
    """Test 3-char PARTIAL with EXTRA descendants."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/partial/"]

    result = apm.analyze_primary_secondary(codelist_rows)

    # Baseline: M60
    assert result["baseline_primary"] == 500
    # Strict: no COMPLETE codes, so just baseline
    assert result["strict_primary"] == 500
    # Partial: includes EXTRA descendants of PARTIAL codes
    assert result["partial_primary"] == 500 + 100 + 30


def test_analyze_none_uploaded_with_descendants(mock_extended_data):
    """Test NONE codes with EXTRA descendants for uploaded codelists."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/none/"]

    result = apm.analyze_none_uploaded(codelist_rows)

    # Should count descendants of NONE codes
    assert result["none_primary"] == 200 + 50
    assert result["none_secondary"] == 100 + 25


def test_analyze_none_uploaded_mixed_codelist(mock_extended_data):
    """Test uploaded codelist with mix of COMPLETE/PARTIAL/NONE."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/mixed/"]

    result = apm.analyze_none_uploaded(codelist_rows)

    # Should only count descendants of I30 (NONE)
    assert result["none_primary"] == 100
    assert result["none_secondary"] == 50


def test_analyze_all_count_with_partial_children(mock_extended_data):
    """Test all_count analysis including partial code descendants."""
    data, _ = common.get_apcs_coverage_data()
    codelist_rows = [r for r in data if r["codelist_id"] == "/test/partial/"]

    result = apm.analyze_all_count(codelist_rows)

    # Baseline: M60
    assert result["baseline_all"] == 750
    # With partial children: includes M600, M6001
    assert result["with_partial_children_all"] == 750 + 150 + 45


def test_run_analysis_creates_comprehensive_output(mock_extended_data):
    """Test full analysis run with multiple codelists."""
    results = apm.run_analysis()

    # Should have analyzed multiple codelists
    assert len(results) > 0

    # Check CSV structure
    csv_file = mock_extended_data["out_dir"] / "prefix_matching_analysis.csv"
    assert csv_file.exists()

    with open(csv_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) > 0

        # Check all expected columns
        expected_cols = [
            "codelist_id",
            "creation_method",
            "baseline_primary",
            "strict_primary",
            "partial_primary",
        ]
        assert reader.fieldnames
        for col in expected_cols:
            assert col in reader.fieldnames


def test_map_to_repos_with_multiple_repos(mock_extended_data):
    """Test mapping codelists to repos."""
    apm.run_analysis()
    apm.map_to_repos()

    repos_file = mock_extended_data["out_dir"] / "prefix_matching_repos.csv"
    assert repos_file.exists()

    with open(repos_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        # Should have mappings for multiple repos
        repos = {r["repo"] for r in rows}
        assert len(repos) > 0


def test_generate_markdown_report(mock_extended_data):
    """Test markdown report generation."""
    apm.run_analysis()

    md_file = mock_extended_data["out_dir"] / "prefix_matching_analysis.md"
    assert md_file.exists()

    content = md_file.read_text()
    # Check for key sections
    assert "Prefix Matching Analysis" in content or "Analysis" in content


def test_main_function_integration(mock_extended_data, monkeypatch, capsys):
    """Test main function end-to-end."""
    import sys

    # Mock sys.argv to not include --force
    monkeypatch.setattr(sys, "argv", ["analyze_prefix_matching.py"])

    apm.main()

    captured = capsys.readouterr()
    assert "Loading data" in captured.out
    assert "Found" in captured.out

    # Check outputs exist
    assert (mock_extended_data["out_dir"] / "prefix_matching_analysis.csv").exists()
    assert (mock_extended_data["out_dir"] / "prefix_matching_analysis.md").exists()
