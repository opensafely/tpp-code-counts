import base64
import json

from reporting_port import common
from reporting_port import generate_reports as reports


def github_response(args):
    """Return enough GitHub data for report rendering without network access."""
    target = " ".join(args)
    if "contents/" in target:
        content = (
            "G906,Causalgia\n"
            "R17,Unspecified jaundice\n"
            "A000,Cholera\n"
            "E10,Type 1 diabetes mellitus\n"
        )
        encoded = base64.b64encode(content.encode()).decode()
        return True, json.dumps({"content": encoded, "encoding": "base64"})
    return True, json.dumps({"default_branch": "main"})


def test_code_search_includes_forks(monkeypatch):
    calls = []

    def capture(args):
        calls.append(args)
        return True, '{"items": []}'

    monkeypatch.setattr(common, "run_gh_command", capture)

    assert common.search_code_in_org("U109") == {}
    assert 'q="U109" org:opensafely' in calls[0]
    assert 'q="U109" org:opensafely fork:true' in calls[1]


def test_framework_split_and_four_vs_two_issues(tmp_path, monkeypatch):
    monkeypatch.setattr(reports, "EMAIL_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(reports, "run_gh_command", github_response)

    all_results = {
        "G906": {
            "opensafely/ehrql-repo": [
                {"path": "codelists/codes.csv", "line_text": "G906,Causalgia"}
            ],
            "opensafely/ce-repo": [
                {"path": "codelists/codes.csv", "line_text": "G906,Causalgia"}
            ],
        },
        "R17": {
            "opensafely/ehrql-repo": [
                {"path": "codelists/codes.csv", "line_text": "R17,Unspecified jaundice"}
            ],
            "opensafely/ce-repo": [
                {"path": "codelists/codes.csv", "line_text": "R17,Unspecified jaundice"}
            ],
        },
    }
    groups = [{"codes": ["G906"], "description": "Causalgia", "actual_codes": ["G564"]}]
    definitions = {
        "R17": {"2016": "Unspecified jaundice", "2019": "Hyperbilirubinaemia"}
    }
    warnings = {
        "ehrql-repo": [
            {
                "codelist": "/test/list/1/",
                "current": "10",
                "x_padded": "20",
                "with_prefix": "30",
            }
        ],
        "ce-repo": [
            {
                "codelist": "/test/list/1/",
                "current": "10",
                "x_padded": "20",
                "with_prefix": "30",
            }
        ],
    }

    reports.generate_repo_emails(
        all_results,
        {"G906": "Causalgia", "R17": "Hyperbilirubinaemia"},
        groups,
        {
            "G564": {
                ("apcs_primary_count", "TOTAL"): 3,
                ("apcs_all_count", "TOTAL"): 7,
            },
            "R17X": {
                ("apcs_primary_count", "TOTAL"): 2,
                ("apcs_all_count", "TOTAL"): 5,
            },
            "R171": {
                ("apcs_primary_count", "TOTAL"): 6,
                ("apcs_all_count", "TOTAL"): 11,
            },
            "A000": {
                ("apcs_primary_count", "TOTAL"): 40,
                ("apcs_all_count", "TOTAL"): 100,
            },
            "E10X": {
                ("apcs_primary_count", "TOTAL"): 10,
                ("apcs_all_count", "TOTAL"): 25,
            },
        },
        warnings,
        definitions,
        {
            "opensafely/ehrql-repo": "ehrql",
            "opensafely/ce-repo": "cohortextractor",
        },
        {
            "/test/list/1/": {
                "x_padded_codes": ["E10"],
                "modifier_codes": ["E1000"],
                "baseline_all": 100,
                "with_x_padding_all": 125,
                "with_prefix_matching_all": 140,
            }
        },
        generated_on="2026-08-14",
    )

    ehrql = (tmp_path / "ehrql" / "ehrql-repo.md").read_text()
    ehrql_x_padding = (tmp_path / "ehrql-x-padding" / "ehrql-repo.md").read_text()
    cohortextractor = (tmp_path / "cohortextractor" / "ce-repo.md").read_text()
    for heading in (
        "Action recommended: modifier codes may be missing",
        "Action recommended: codes may be missing",
        "Action required: code descriptions differ",
    ):
        assert heading in ehrql
    assert "Action recommended: codes may be missing" in cohortextractor
    assert "Action required: code descriptions differ" in cohortextractor
    assert "missing 'X' padded codes" not in ehrql
    assert "Action recommended: missing 'X' padded codes" in ehrql_x_padding
    assert "modifier codes may be missing" not in ehrql_x_padding
    assert "codes may be missing" not in ehrql_x_padding
    assert "code descriptions differ" not in ehrql_x_padding
    assert "modifier codes may be missing" not in cohortextractor
    assert "missing 'X' padded codes" not in cohortextractor
    assert "_Generated on 2026-08-14_" in ehrql
    assert "For each affected codelist" not in ehrql
    assert "`E10`" in ehrql_x_padding
    assert "`E1000`" in ehrql
    assert (
        "Codelist currently matches: 20 events in `primary_diagnosis` and "
        "125 events in `all_diagnoses`"
    ) in ehrql
    assert (
        "Codelist would match: 30 events in `primary_diagnosis` and 140 events "
        "in `all_diagnoses`"
    ) in ehrql
    assert (
        "Codelist currently matches: 52 events in `primary_diagnosis` and "
        "130 events in `all_diagnoses`"
    ) in ehrql
    assert (
        "Codelist would match: 55 events in `primary_diagnosis` and 137 events "
        "in `all_diagnoses`"
    ) in ehrql
    assert "Codelist currently matches: 141 APCS events" in cohortextractor
    assert (
        "Codelist would match: 125 APCS events if all codes with differing "
        "descriptions were removed"
    ) in cohortextractor


def test_codelist_usage_deduplicates_three_character_and_x_padded_codes():
    usage = {"E10X": {("apcs_all_count", "TOTAL"): 25}}

    assert reports.codelist_usage_total(usage, {"E10", "E10X"}) == 25


def test_codelist_usage_uses_minimal_prefixes_for_cohortextractor():
    usage = {
        "S10X": {("apcs_all_count", "TOTAL"): 1},
        "S101": {("apcs_all_count", "TOTAL"): 2},
        "S1015": {("apcs_all_count", "TOTAL"): 4},
        "S20X": {("apcs_all_count", "TOTAL"): 8},
        "S305": {("apcs_all_count", "TOTAL"): 16},
        "T10X": {("apcs_all_count", "TOTAL"): 32},
    }
    codes = {"S10", "S101", "S102", "S20", "S30", "S305"}

    assert reports.minimal_prefixes(codes) == {"S10", "S20", "S30"}
    assert reports.codelist_usage_total(usage, codes, prefix_matching=True) == 31


def test_prefix_only_ehrql_repository_gets_a_report(tmp_path, monkeypatch):
    monkeypatch.setattr(reports, "EMAIL_OUTPUT_DIR", tmp_path)
    reports.generate_repo_emails(
        {},
        {},
        [],
        {},
        {
            "prefix-only": [
                {
                    "codelist": "list",
                    "current": "1",
                    "x_padded": "2",
                    "with_prefix": "2",
                }
            ]
        },
        project_types={"opensafely/prefix-only": "ehrql"},
        prefix_details={
            "list": {
                "x_padded_codes": ["I64"],
                "modifier_codes": [],
                "baseline_all": 3,
                "with_x_padding_all": 4,
                "with_prefix_matching_all": 4,
            }
        },
    )
    assert not (tmp_path / "ehrql" / "prefix-only.md").exists()
    content = (tmp_path / "ehrql-x-padding" / "prefix-only.md").read_text()
    assert "Action recommended: missing 'X' padded codes" in content
    assert "modifier codes may be missing" not in content
    assert "## Action recommended: codes may be missing" not in content
    assert "`I64`" in content


def test_cohortextractor_covered_prefix_is_suppressed(monkeypatch):
    monkeypatch.setattr(
        common,
        "get_project_type",
        lambda repo, overrides=None: "cohortextractor",
    )
    monkeypatch.setattr(
        common,
        "load_github_repo_file",
        lambda repo, path: "code,description\nK58,Irritable bowel syndrome\n",
    )
    results = {
        "K581": {
            "opensafely/example": [
                {"path": "codelists/ibs.csv", "line_text": "K581,IBS with diarrhoea"}
            ]
        }
    }
    groups = [{"codes": ["K581"], "actual_codes": ["K580"]}]

    filtered, project_types = common.filter_cohortextractor_moved_codes(results, groups)

    assert filtered == {}
    assert project_types == {"opensafely/example": "cohortextractor"}


def test_chapter_codelist_exceptions(tmp_path, monkeypatch):
    monkeypatch.setattr(reports, "EMAIL_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(reports, "run_gh_command", github_response)
    chapter_ii = "codelists/opensafely-icd-10-chapter-ii.csv"
    chapter_i = "codelists/opensafely-icd-10-chapter-i.csv"
    matches = {
        "G906": {
            "opensafely/ehrql-repo": [
                {"path": chapter_ii, "line_text": "G906,Causalgia"}
            ],
            "opensafely/ce-repo": [{"path": chapter_ii, "line_text": "G906,Causalgia"}],
        },
        "A925": {
            repo: [{"path": chapter_i, "line_text": "A925,Zika virus disease"}]
            for repo in ("opensafely/ehrql-repo", "opensafely/ce-repo")
        },
        "B485": {
            repo: [{"path": chapter_i, "line_text": "B485,Pneumocystosis"}]
            for repo in ("opensafely/ehrql-repo", "opensafely/ce-repo")
        },
    }
    groups = [
        {"codes": ["G906"], "description": "Causalgia", "actual_codes": ["G564"]},
        {
            "codes": ["A925"],
            "description": "Personal history of COVID-19",
            "actual_codes": ["U06", "U069"],
        },
        {"codes": ["B485"], "description": "Pneumocystosis", "actual_codes": ["B59"]},
    ]

    reports.generate_repo_emails(
        matches,
        {"G906": "Causalgia", "A925": "Zika", "B485": "Pneumocystosis"},
        groups,
        {},
        {},
        project_types={
            "opensafely/ehrql-repo": "ehrql",
            "opensafely/ce-repo": "cohortextractor",
        },
    )

    ehrql = (tmp_path / "ehrql" / "ehrql-repo.md").read_text()
    cohortextractor = (tmp_path / "cohortextractor" / "ce-repo.md").read_text()
    assert "Causalgia" in ehrql
    assert "Causalgia" not in cohortextractor
    for report in (ehrql, cohortextractor):
        assert "Pneumocystosis" in report
        assert "`B59`" in report
        assert "Personal history of COVID-19" not in report
        assert "`U06`" not in report
        assert "`U069`" not in report


def test_r17_in_openpregnosis_is_excluded_from_cached_results():
    results = {
        "R17": {
            "OpenPregnosis": [
                {
                    "path": "analysis/22_hes_diagnostic_event_counts.py",
                    "line_text": '"R17",',
                }
            ],
            "another-repo": [
                {
                    "path": "codelists/icd10.csv",
                    "line_text": "R17,Hyperbilirubinaemia",
                }
            ],
        }
    }

    assert common.filter_github_search_results(results) == {
        "R17": {"another-repo": results["R17"]["another-repo"]}
    }


def test_non_actionable_broad_codelist_findings_are_excluded():
    results = {
        "X670": {
            "MH_pandemic": [
                {
                    "path": "codelists/ons-self-harm.csv",
                    "line_text": "X670,Intentional self-poisoning",
                }
            ]
        },
        "W268": {
            "PostOpCovid": [
                {
                    "path": "codelists/user-colincrooks-procedurecategory.csv",
                    "line_text": "W268,Other specified closed reduction,Orthopaedic",
                }
            ]
        },
        "W269": {
            "PostOpCovid": [
                {
                    "path": "codelists/user-colincrooks-procedurecategory.csv",
                    "line_text": "W269,Unspecified closed reduction,Orthopaedic",
                }
            ]
        },
        "I620": {
            "surgery-research": [
                {
                    "path": (
                        "codelists/user-salmachaudhury-surgery-complication-icd-10-"
                        "codes-veno-thromboembolic-disease.csv"
                    ),
                    "line_text": "I620,Nontraumatic subdural haemorrhage",
                }
            ],
            "another-repo": [
                {
                    "path": "codelists/neurology.csv",
                    "line_text": "I620,Nontraumatic subdural haemorrhage",
                }
            ],
        },
    }

    assert common.filter_github_search_results(results) == {
        "X670": {},
        "W268": {},
        "W269": {},
        "I620": {"another-repo": results["I620"]["another-repo"]},
    }


def test_input_files_load():
    moved_codes, groups = common.load_swapped_codes()
    changed = common.load_changed_code_definitions()
    warnings = common.load_prefix_matching_warnings()
    details = common.load_prefix_matching_details()
    usage, _ = common.load_usage_data()

    assert moved_codes and groups
    assert changed
    assert warnings
    assert details
    assert details["/user/elsie_horne/dvt_icvt_icd10/30a4dcad/"] == {
        "x_padded_codes": ["G08"],
        "modifier_codes": [],
        "baseline_all": 400,
        "with_x_padding_all": 1680,
        "with_prefix_matching_all": 1680,
    }
    assert usage
