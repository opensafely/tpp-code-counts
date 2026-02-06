"""Tests for reporting/generate_consolidated_reports.py module."""

import json
from pathlib import Path

import pytest

from reporting import generate_consolidated_reports as gcr
from reporting import common


@pytest.fixture
def mock_consolidated_data(tmp_path, monkeypatch):
    """Create mock data files for consolidated report tests."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "outputs"

    data_dir.mkdir()
    out_dir.mkdir()

    # Create repo project number CSV
    repo_project_file = data_dir / "repo_projectnumber.csv"
    repo_project_file.write_text(
        "number,name,slug,url\n"
        "123,Test Project,test-project,https://github.com/opensafely/test-repo\n"
        "456,Another Project,another-project,https://github.com/opensafely/another-repo\n"
    )

    # Create swapped codes JSON
    swapped_codes_file = data_dir / "swapped_codes.json"
    swapped_data = {
        "codes": {
            "G906": "Encephalopathy",
            "U071": "COVID-19",
            "K580": "IBS with diarrhea",
        },
        "groups": [
            {
                "codes": ["G906"],
                "description": "Encephalopathy",
                "actual_codes": ["G930", "G931"],
            }
        ],
    }
    swapped_codes_file.write_text(json.dumps(swapped_data))

    # Create usage data
    usage_file = data_dir / "code_usage_apcs_2024-04_2025-03.csv"
    usage_file.write_text(
        "icd10_code,field,position,count\n"
        "G930,apcs_primary_diagnosis,TOTAL,1000\n"
        "G930,apcs_primary_diagnosis,2024-25,800\n"
        "G931,apcs_primary_diagnosis,2024-25,500\n"
        "E10,apcs_primary_diagnosis,2024-25,1000\n"
        "E100,apcs_primary_diagnosis,2024-25,200\n"
        "E101,apcs_primary_diagnosis,2024-25,150\n"
        "A33X,apcs_primary_diagnosis,2024-25,50\n"
    )

    # Create coverage detail file
    coverage_file = out_dir / "codelist_coverage_detail_apcs.csv"
    coverage_file.write_text(
        "codelist_id,creation_method,Exists in ehrQL repo,icd10_code,status,apcs_primary_count,apcs_secondary_count,apcs_all_count\n"
        "/test/codelist/1/,Builder,Y,E10,COMPLETE,1000,500,1500\n"
        "/test/codelist/1/,Builder,Y,E100,EXTRA,200,100,300\n"
        "/test/codelist/2/,Builder,Y,A33,COMPLETE,0,0,0\n"
        "/test/codelist/2/,Builder,Y,A33X,EXTRA,50,20,70\n"
    )

    # Create prefix matching warnings
    prefix_warnings_file = data_dir / "prefix_matching_warnings.json"
    prefix_warnings_data = {
        "test-repo": [
            {
                "codelist": "/test/codelist/1/",
                "current": "1000",
                "x_padded": "1000",
                "with_prefix": "1350",
            }
        ]
    }
    prefix_warnings_file.write_text(json.dumps(prefix_warnings_data))

    monkeypatch.setattr(common, "DATA_DIR", data_dir)
    monkeypatch.setattr(common, "OUT_DIR", out_dir)
    monkeypatch.setattr(common, "COVERAGE_APCS_FILE", coverage_file)
    monkeypatch.setattr(gcr, "REPO_PROJECT_NUMBER_FILE", repo_project_file)
    monkeypatch.setattr(gcr, "MOVED_CODES_REPORT", out_dir / "moved_codes_report.md")
    monkeypatch.setattr(
        gcr, "PREFIX_MATCHING_REPORT", out_dir / "prefix_matching_report.md"
    )

    return {
        "data_dir": data_dir,
        "out_dir": out_dir,
    }


def test_load_repo_project_numbers(mock_consolidated_data):
    """Test loading repo to project number mapping."""
    repo_map = gcr.load_repo_project_numbers()

    assert "test-repo" in repo_map
    assert repo_map["test-repo"]["number"] == "123"
    assert repo_map["test-repo"]["name"] == "Test Project"
    assert repo_map["test-repo"]["slug"] == "test-project"


def test_load_repo_project_numbers_missing_file(tmp_path, monkeypatch):
    """Test handling when project number file doesn't exist."""
    monkeypatch.setattr(gcr, "REPO_PROJECT_NUMBER_FILE", tmp_path / "missing.csv")

    repo_map = gcr.load_repo_project_numbers()

    assert repo_map == {}


def test_calculate_usage_scenarios(mock_consolidated_data):
    """Test calculating the three usage scenarios."""
    usage_totals = {
        "E10": {("apcs_primary_count", "2024-25"): 1000},
        "E100": {("apcs_primary_count", "2024-25"): 200},
        "E101": {("apcs_primary_count", "2024-25"): 150},
        "E10X": {("apcs_primary_count", "2024-25"): 50},
    }

    codelist_codes = ["E10"]

    exact, with_prefix, with_x = gcr.calculate_usage_scenarios(
        usage_totals, codelist_codes
    )

    # Exact should only include E10
    assert exact == 1000

    # With prefix should include E10, E100, E101, E10X (all codes starting with E10)
    assert with_prefix == 1400

    # With X padding should include E10 and E10X
    assert with_x == 1050


def test_calculate_usage_scenarios_three_char_code(mock_consolidated_data):
    """Test X-padding for 3-character codes."""
    usage_totals = {
        "A33": {("apcs_primary_count", "2024-25"): 0},
        "A33X": {("apcs_primary_count", "2024-25"): 50},
    }

    codelist_codes = ["A33"]

    exact, with_prefix, with_x = gcr.calculate_usage_scenarios(
        usage_totals, codelist_codes
    )

    assert exact == 0
    assert with_x == 50  # Should add A33X


def test_calculate_usage_scenarios_empty_codelist():
    """Test handling of empty codelist."""
    usage_totals = {"E10": {("apcs_primary_count", "2024-25"): 1000}}
    codelist_codes = []

    exact, with_prefix, with_x = gcr.calculate_usage_scenarios(
        usage_totals, codelist_codes
    )

    assert exact == 0
    assert with_prefix == 0
    assert with_x == 0


def test_generate_moved_codes_report(mock_consolidated_data):
    """Test generating moved codes report."""
    codes = {"G906": "Encephalopathy"}
    groups = [
        {
            "codes": ["G906"],
            "description": "Encephalopathy",
            "actual_codes": ["G930", "G931"],
        }
    ]
    usage_totals = {
        "G930": {("apcs_all_count", "TOTAL"): 1000},
        "G931": {("apcs_all_count", "TOTAL"): 500},
    }
    repo_project_map = {
        "test-repo": {
            "number": "123",
            "name": "Test Project",
            "slug": "test-project",
            "url": "https://github.com/opensafely/test-repo",
        }
    }

    all_results = {
        "G906": {
            "opensafely/test-repo": [
                {"path": "analysis/study.py", "line_text": 'code="G906"'}
            ]
        }
    }

    gcr.generate_moved_codes_report(
        all_results, codes, groups, usage_totals, repo_project_map
    )

    report_file = mock_consolidated_data["out_dir"] / "moved_codes_report.md"
    assert report_file.exists()

    content = report_file.read_text()
    assert "Moved ICD-10 Codes Report" in content
    assert "test-repo" in content
    assert "G906" in content
    assert "Encephalopathy" in content


def test_generate_moved_codes_report_no_matches(mock_consolidated_data, capsys):
    """Test handling when no repos have moved codes."""
    codes = {}
    groups = []
    usage_totals = {}
    repo_project_map = {}
    all_results = {}

    gcr.generate_moved_codes_report(
        all_results, codes, groups, usage_totals, repo_project_map
    )

    captured = capsys.readouterr()
    assert "No projects found with moved codes" in captured.out


def test_generate_prefix_matching_report(mock_consolidated_data, monkeypatch):
    """Test generating prefix matching report."""

    # Mock load_usage_data to return proper format
    def mock_load_usage_data(source):
        return {
            "E10": {("apcs_primary_count", "2024-25"): 1000},
            "E100": {("apcs_primary_count", "2024-25"): 200},
            "E101": {("apcs_primary_count", "2024-25"): 150},
        }, []

    monkeypatch.setattr(common, "load_usage_data", mock_load_usage_data)

    prefix_warnings = {
        "test-repo": [
            {
                "codelist": "/test/codelist/1/",
                "current": "1000",
                "x_padded": "1000",
                "with_prefix": "1350",
            }
        ]
    }

    usage_totals = {
        "E10": {("apcs_primary_count", "2024-25"): 1000},
        "E100": {("apcs_primary_count", "2024-25"): 200},
        "E101": {("apcs_primary_count", "2024-25"): 150},
    }

    codelist_codes = {"/test/codelist/1/": ["E10"]}

    repo_project_map = {
        "test-repo": {
            "number": "123",
            "name": "Test Project",
            "slug": "test-project",
            "url": "https://github.com/opensafely/test-repo",
        }
    }

    gcr.generate_prefix_matching_report(
        prefix_warnings, usage_totals, codelist_codes, repo_project_map
    )

    report_file = mock_consolidated_data["out_dir"] / "prefix_matching_report.md"
    assert report_file.exists()

    content = report_file.read_text()
    assert "Prefix Matching Issues Report" in content
    assert "test-repo" in content
    assert "/test/codelist/1/" in content
    assert "1,000" in content  # Formatted number


def test_generate_prefix_matching_report_no_warnings(mock_consolidated_data, capsys):
    """Test handling when no prefix matching warnings exist."""
    prefix_warnings = {}
    usage_totals = {}
    codelist_codes = {}
    repo_project_map = {}

    gcr.generate_prefix_matching_report(
        prefix_warnings, usage_totals, codelist_codes, repo_project_map
    )

    captured = capsys.readouterr()
    assert "No projects found with prefix matching issues" in captured.out


def test_generate_prefix_matching_report_with_percentages(mock_consolidated_data):
    """Test that percentage increases are calculated correctly."""
    prefix_warnings = {
        "test-repo": [
            {
                "codelist": "/test/codelist/1/",
                "current": "1000",
                "x_padded": "1200",
                "with_prefix": "1500",
            }
        ]
    }

    usage_totals = {
        "E10": {("apcs_primary_count", "2024-25"): 1000},
        "E100": {("apcs_primary_count", "2024-25"): 200},
        "E101": {("apcs_primary_count", "2024-25"): 300},
    }

    codelist_codes = {"/test/codelist/1/": ["E10"]}

    repo_project_map = {}

    gcr.generate_prefix_matching_report(
        prefix_warnings, usage_totals, codelist_codes, repo_project_map
    )

    report_file = mock_consolidated_data["out_dir"] / "prefix_matching_report.md"
    content = report_file.read_text()

    # Check for percentage increases
    assert "%" in content
    assert "increase" in content
