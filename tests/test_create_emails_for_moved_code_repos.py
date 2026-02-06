"""Tests for reporting/create_emails_for_moved_code_repos.py module."""

import json

import pytest

from reporting import common
from reporting import create_emails_for_moved_code_repos as cemcr


@pytest.fixture
def mock_email_data(tmp_path, monkeypatch):
    """Create mock data files for email generation tests."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "outputs"
    email_dir = tmp_path / "repo_emails"

    data_dir.mkdir()
    out_dir.mkdir()
    email_dir.mkdir()

    # Create swapped codes JSON - format expected by load_swapped_codes
    swapped_codes_file = data_dir / "swapped_codes.json"
    swapped_data = [
        {
            "codes": ["G906"],
            "description": "Encephalopathy",
            "actual_codes": ["G930", "G931"],
        },
        {
            "codes": ["U071"],
            "description": "COVID-19 virus identified",
            "actual_codes": ["U071"],
        },
        {
            "codes": ["K580", "K581"],
            "description": "Irritable bowel syndrome",
            "actual_codes": ["K580", "K588"],
        },
    ]
    swapped_codes_file.write_text(json.dumps(swapped_data))

    # Create usage data CSV
    usage_file = data_dir / "code_usage_apcs_2024-04_2025-03.csv"
    usage_file.write_text(
        "icd10_code,field,position,count\n"
        "G930,apcs_primary_diagnosis,TOTAL,1000\n"
        "G931,apcs_primary_diagnosis,TOTAL,500\n"
        "K580,apcs_all_diagnosis,TOTAL,2000\n"
    )

    # Create prefix matching warnings JSON
    prefix_warnings_file = data_dir / "prefix_matching_warnings.json"
    prefix_warnings_data = {
        "test-repo": [
            {
                "codelist": "/test/codelist/1/",
                "current": "1000",
                "x_padded": "1200",
                "with_prefix": "1500",
            }
        ]
    }
    prefix_warnings_file.write_text(json.dumps(prefix_warnings_data))

    # Create GitHub search cache
    cache_file = data_dir / "github_code_search_cache.json"
    cache_data = {
        "G906": {
            "opensafely/test-repo": [
                {
                    "path": "analysis/study_definition.py",
                    "line_text": '    icd10_code="G906",',
                }
            ]
        },
        "K580": {
            "opensafely/test-repo": [
                {
                    "path": "analysis/study_definition.py",
                    "line_text": '    icd10_code="K580",',
                }
            ],
            "opensafely/another-repo": [
                {"path": "codelists/k58.csv", "line_text": "K580,IBS with diarrhea"}
            ],
        },
    }
    cache_file.write_text(json.dumps(cache_data))

    monkeypatch.setattr(common, "DATA_DIR", data_dir)
    monkeypatch.setattr(common, "OUT_DIR", out_dir)
    monkeypatch.setattr(common, "SWAPPED_CODES_FILE", swapped_codes_file)
    monkeypatch.setattr(common, "GITHUB_CACHE_FILE", cache_file)
    monkeypatch.setattr(cemcr, "EMAIL_OUTPUT_DIR", email_dir)

    # Mock load_usage_data to return the test data
    def mock_load_usage_data(source):
        return {
            "G930": {("apcs_all_count", "TOTAL"): 1000},
            "G931": {("apcs_all_count", "TOTAL"): 500},
            "K580": {("apcs_all_count", "TOTAL"): 2000},
        }, []

    monkeypatch.setattr(common, "load_usage_data", mock_load_usage_data)

    # Mock load_prefix_matching_warnings
    def mock_load_prefix_warnings():
        return prefix_warnings_data

    monkeypatch.setattr(
        common, "load_prefix_matching_warnings", mock_load_prefix_warnings
    )

    return {
        "data_dir": data_dir,
        "out_dir": out_dir,
        "email_dir": email_dir,
        "cache_data": cache_data,
    }


def test_generate_repo_emails_creates_files(mock_email_data):
    """Test that email files are created for each repo."""
    codes = {"G906": "Encephalopathy", "K580": "IBS with diarrhea"}
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

    cemcr.generate_repo_emails(
        mock_email_data["cache_data"], codes, groups, usage_totals, prefix_warnings
    )

    # Check that email files were created
    email_dir = mock_email_data["email_dir"]
    email_files = list(email_dir.glob("*.md"))

    assert len(email_files) > 0
    assert (email_dir / "test-repo.md").exists()


def test_email_contains_prefix_warnings(mock_email_data, monkeypatch):
    """Test that prefix warnings appear in the email."""

    # Mock GitHub API calls
    def mock_run_gh_command(args):
        if "repos/opensafely/" in " ".join(args):
            if "contents/" in " ".join(args):
                # Return mock file contents
                import base64

                content = 'icd10_code="G906",\n'
                encoded = base64.b64encode(content.encode()).decode()
                return True, json.dumps({"content": encoded, "encoding": "base64"})
            else:
                # Return mock repo info
                return True, json.dumps({"default_branch": "main"})
        return True, ""

    monkeypatch.setattr(common, "run_gh_command", mock_run_gh_command)

    codes = {"G906": "Encephalopathy"}
    groups = []
    usage_totals = {}
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

    all_results = {
        "G906": {
            "opensafely/test-repo": [
                {"path": "analysis/study.py", "line_text": 'icd10_code="G906"'}
            ]
        }
    }

    cemcr.generate_repo_emails(
        all_results, codes, groups, usage_totals, prefix_warnings
    )

    # Read the email file
    email_file = mock_email_data["email_dir"] / "test-repo.md"
    content = email_file.read_text()

    # Check for prefix warning section
    assert "Prefix Matching Warning" in content
    assert "1,000" in content  # Formatted number
    assert "1,200" in content
    assert "1,500" in content


def test_email_contains_moved_codes(mock_email_data, monkeypatch):
    """Test that moved codes section appears in the email."""

    # Mock GitHub API calls
    def mock_run_gh_command(args):
        if "repos/opensafely/" in " ".join(args):
            if "contents/" in " ".join(args):
                import base64

                content = 'icd10_code="G906",\n'
                encoded = base64.b64encode(content.encode()).decode()
                return True, json.dumps({"content": encoded, "encoding": "base64"})
            else:
                return True, json.dumps({"default_branch": "main"})
        return True, ""

    monkeypatch.setattr(common, "run_gh_command", mock_run_gh_command)

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
    prefix_warnings = {}

    all_results = {
        "G906": {
            "opensafely/test-repo": [
                {"path": "analysis/study.py", "line_text": 'icd10_code="G906"'}
            ]
        }
    }

    cemcr.generate_repo_emails(
        all_results, codes, groups, usage_totals, prefix_warnings
    )

    # Read the email file
    email_file = mock_email_data["email_dir"] / "test-repo.md"
    content = email_file.read_text()

    # Check for moved codes section
    assert "Codes that moved" in content or "codes that moved" in content
    assert "G906" in content
    assert "Encephalopathy" in content
    assert "G930" in content
    assert "G931" in content


def test_email_with_multiple_files(mock_email_data, monkeypatch):
    """Test email generation with matches in multiple files."""

    def mock_run_gh_command(args):
        if "repos/opensafely/" in " ".join(args):
            if "contents/" in " ".join(args):
                import base64

                if "study.py" in " ".join(args):
                    content = 'icd10_code="G906",\n'
                else:
                    content = "G906,Encephalopathy\n"
                encoded = base64.b64encode(content.encode()).decode()
                return True, json.dumps({"content": encoded, "encoding": "base64"})
            else:
                return True, json.dumps({"default_branch": "main"})
        return True, ""

    monkeypatch.setattr(common, "run_gh_command", mock_run_gh_command)

    codes = {"G906": "Encephalopathy"}
    groups = []
    usage_totals = {}
    prefix_warnings = {}

    all_results = {
        "G906": {
            "opensafely/test-repo": [
                {"path": "analysis/study.py", "line_text": 'icd10_code="G906"'},
                {"path": "codelists/g90.csv", "line_text": "G906,Encephalopathy"},
            ]
        }
    }

    cemcr.generate_repo_emails(
        all_results, codes, groups, usage_totals, prefix_warnings
    )

    # Read the email file
    email_file = mock_email_data["email_dir"] / "test-repo.md"
    content = email_file.read_text()

    # Check both files appear
    assert "analysis/study.py" in content
    assert "codelists/g90.csv" in content


def test_email_clears_old_files(mock_email_data):
    """Test that old email files are removed."""
    email_dir = mock_email_data["email_dir"]

    # Create an old file
    old_file = email_dir / "old-repo.md"
    old_file.write_text("Old content")

    assert old_file.exists()

    codes = {}
    groups = []
    usage_totals = {}
    prefix_warnings = {}
    all_results = {}

    cemcr.generate_repo_emails(
        all_results, codes, groups, usage_totals, prefix_warnings
    )

    # Old file should be removed
    assert not old_file.exists()


def test_main_checks_gh_cli(monkeypatch, mock_email_data):
    """Test that main checks for gh CLI availability."""

    def mock_run_gh_command_fail(args):
        return False, ""

    monkeypatch.setattr(common, "run_gh_command", mock_run_gh_command_fail)

    with pytest.raises(SystemExit) as exc_info:
        cemcr.main()

    assert exc_info.value.code == 1
