"""Extended tests for generate_consolidated_reports.py to reach 90%+ coverage."""

import pytest

from reporting import generate_consolidated_reports as gcr


@pytest.fixture
def mock_data_extended(tmp_path, monkeypatch):
    """Create extended mock data."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "outputs"

    data_dir.mkdir()
    out_dir.mkdir()

    # Repo project file with error handling cases
    repo_project_file = data_dir / "repo_projectnumber.csv"
    repo_project_file.write_text(
        "number,name,slug,url\n"
        "123,Test Project,test-project,https://github.com/opensafely/test-repo\n"
        ",,, \n"  # Empty row
        "456,No URL Project,no-url,\n"  # Missing URL
        "789,Bad URL,bad-url,https://example.com/other/path\n"  # Non-opensafely URL
    )

    usage_file = data_dir / "code_usage_apcs_2024-04_2025-03.csv"
    usage_file.write_text(
        "icd10_code,field,position,count\n"
        "K580,apcs_primary_diagnosis,2024-25,500\n"
        "U071,apcs_primary_diagnosis,2024-25,1000\n"
        "G906,apcs_primary_diagnosis,2024-25,800\n"
        "X999,apcs_primary_diagnosis,2024-25,100\n"
    )

    coverage_file = out_dir / "codelist_coverage_detail_apcs.csv"
    coverage_file.write_text(
        "codelist_id,creation_method,Exists in ehrQL repo,icd10_code,status,apcs_primary_count\n"
        "/test/k58/,Builder,Y,K58,COMPLETE,500\n"
        "/test/u07/,Builder,Y,U07,COMPLETE,1000\n"
        "/test/g90/,Builder,Y,G90,COMPLETE,800\n"
        "/test/x99/,Builder,Y,X99,COMPLETE,100\n"
    )

    monkeypatch.setattr(gcr, "REPO_PROJECT_NUMBER_FILE", repo_project_file)
    monkeypatch.setattr(gcr, "MOVED_CODES_REPORT", out_dir / "moved_codes_report.md")
    monkeypatch.setattr(
        gcr, "PREFIX_MATCHING_REPORT", out_dir / "prefix_matching_report.md"
    )

    return {"data_dir": data_dir, "out_dir": out_dir}


def test_load_repo_project_numbers_with_errors(mock_data_extended):
    """Test loading repo numbers with various error conditions."""
    repo_map = gcr.load_repo_project_numbers()

    # Should only get the valid entry
    assert "test-repo" in repo_map
    assert "no-url" not in repo_map  # No URL
    assert "bad-url" not in repo_map  # Wrong URL format


def test_load_repo_project_numbers_file_read_error(tmp_path, monkeypatch, capsys):
    """Test handling when file can't be read."""
    bad_file = tmp_path / "nonexistent.csv"
    monkeypatch.setattr(gcr, "REPO_PROJECT_NUMBER_FILE", bad_file)

    repo_map = gcr.load_repo_project_numbers()

    assert repo_map == {}
    captured = capsys.readouterr()
    assert "INFO: Repo project number file not found" in captured.out


def test_generate_moved_codes_report_k58_group(mock_data_extended, monkeypatch):
    """Test moved codes report with K58 group."""
    from reporting import common

    def mock_load_usage_data(source):
        return {
            "K580": {("apcs_all_count", "TOTAL"): 500},
        }, []

    monkeypatch.setattr(common, "load_usage_data", mock_load_usage_data)

    codes = {"K580": "IBS with diarrhea"}
    groups = [{"codes": ["K580"], "description": "IBS", "actual_codes": ["K580"]}]
    usage_totals = {"K580": {("apcs_all_count", "TOTAL"): 500}}
    repo_project_map = {}

    all_results = {
        "K580": {"opensafely/test-repo": [{"path": "file.py", "line_text": "K580"}]}
    }

    gcr.generate_moved_codes_report(
        all_results, codes, groups, usage_totals, repo_project_map
    )

    report_file = mock_data_extended["out_dir"] / "moved_codes_report.md"
    assert report_file.exists()
    content = report_file.read_text()
    assert "K580" in content
    assert "2019 edition" in content


def test_generate_moved_codes_report_u_group(mock_data_extended, monkeypatch):
    """Test moved codes report with U codes group."""
    from reporting import common

    def mock_load_usage_data(source):
        return {
            "U071": {("apcs_all_count", "TOTAL"): 1000},
        }, []

    monkeypatch.setattr(common, "load_usage_data", mock_load_usage_data)

    codes = {"U071": "COVID-19"}
    groups = [{"codes": ["U071"], "description": "COVID-19", "actual_codes": ["U071"]}]
    usage_totals = {"U071": {("apcs_all_count", "TOTAL"): 1000}}
    repo_project_map = {}

    all_results = {
        "U071": {"opensafely/test-repo": [{"path": "file.py", "line_text": "U071"}]}
    }

    gcr.generate_moved_codes_report(
        all_results, codes, groups, usage_totals, repo_project_map
    )

    report_file = mock_data_extended["out_dir"] / "moved_codes_report.md"
    content = report_file.read_text()
    assert "U071" in content
    assert "ONS deaths data" in content
    assert "HES APCS data" in content


def test_generate_moved_codes_report_other_group(mock_data_extended, monkeypatch):
    """Test moved codes report with non-G906/K58/U group."""
    from reporting import common

    def mock_load_usage_data(source):
        return {
            "X999": {("apcs_all_count", "TOTAL"): 100},
        }, []

    monkeypatch.setattr(common, "load_usage_data", mock_load_usage_data)

    codes = {"X999": "Other code"}
    groups = [{"codes": ["X999"], "description": "Other", "actual_codes": ["X999"]}]
    usage_totals = {"X999": {("apcs_all_count", "TOTAL"): 100}}
    repo_project_map = {}

    all_results = {
        "X999": {"opensafely/test-repo": [{"path": "file.py", "line_text": "X999"}]}
    }

    gcr.generate_moved_codes_report(
        all_results, codes, groups, usage_totals, repo_project_map
    )

    report_file = mock_data_extended["out_dir"] / "moved_codes_report.md"
    content = report_file.read_text()
    assert "X999" in content


def test_generate_moved_codes_report_write_error(tmp_path, monkeypatch, capsys):
    """Test error handling when report can't be written."""
    import os

    # Create a read-only directory
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    report_file = readonly_dir / "report.md"

    monkeypatch.setattr(gcr, "MOVED_CODES_REPORT", report_file)

    # Make directory read-only after setting up
    os.chmod(readonly_dir, 0o444)

    try:
        gcr.generate_moved_codes_report({}, {}, [], {}, {})
        capsys.readouterr()
        # Should not crash, should handle error
    finally:
        # Restore permissions for cleanup
        os.chmod(readonly_dir, 0o755)


def test_generate_prefix_matching_report_write_error(tmp_path, monkeypatch, capsys):
    """Test error handling when prefix matching report can't be written."""
    import os

    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    report_file = readonly_dir / "report.md"

    monkeypatch.setattr(gcr, "PREFIX_MATCHING_REPORT", report_file)

    os.chmod(readonly_dir, 0o444)

    try:
        prefix_warnings = {
            "test-repo": [
                {
                    "codelist": "/test/",
                    "current": "100",
                    "x_padded": "150",
                    "with_prefix": "200",
                }
            ]
        }
        gcr.generate_prefix_matching_report(prefix_warnings, {}, {}, {})
        capsys.readouterr()
    finally:
        os.chmod(readonly_dir, 0o755)


def test_main_function(mock_data_extended, monkeypatch):
    """Test main function integration."""
    from reporting import common

    # Mock all dependencies
    def mock_load_swapped_codes():
        return {"G906": "Encephalopathy"}, [
            {
                "codes": ["G906"],
                "description": "Encephalopathy",
                "actual_codes": ["G930"],
            }
        ]

    def mock_find_all_codes(codes, force):
        return {
            "G906": {"opensafely/test-repo": [{"path": "file.py", "line_text": "G906"}]}
        }

    def mock_load_usage_data(source):
        return {"G930": {("apcs_all_count", "TOTAL"): 1000}}, []

    def mock_load_prefix_warnings():
        return {
            "test-repo": [
                {
                    "codelist": "/test/",
                    "current": "100",
                    "x_padded": "150",
                    "with_prefix": "200",
                }
            ]
        }

    def mock_get_apcs_coverage_data():
        return [], {"/test/": ["E10"]}

    monkeypatch.setattr(common, "load_swapped_codes", mock_load_swapped_codes)
    monkeypatch.setattr(common, "find_all_codes_in_github", mock_find_all_codes)
    monkeypatch.setattr(common, "load_usage_data", mock_load_usage_data)
    monkeypatch.setattr(
        common, "load_prefix_matching_warnings", mock_load_prefix_warnings
    )
    monkeypatch.setattr(common, "get_apcs_coverage_data", mock_get_apcs_coverage_data)

    gcr.main()

    # Check moved codes report was created
    assert (mock_data_extended["out_dir"] / "moved_codes_report.md").exists()
    # Prefix report may not be created if no warnings found
