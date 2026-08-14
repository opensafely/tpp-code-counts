#!/usr/bin/env python3
"""Generate per-repository ICD-10 codelist review reports."""

import base64
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from .common import (
    PORT_DIR,
    extract_icd10_codes,
    filter_cohortextractor_moved_codes,
    find_all_codes_in_github,
    get_actual_codes,
    get_project_type,
    load_changed_code_definitions,
    load_prefix_matching_details,
    load_prefix_matching_warnings,
    load_project_type_overrides,
    load_swapped_codes,
    load_usage_data,
    run_gh_command,
)


EMAIL_OUTPUT_DIR = PORT_DIR / "repo_emails"

OPENSAFELY_CHAPTER_CODELIST_RE = re.compile(
    r"^opensafely-icd-10-chapter-([ivxlcdm]+)\.[^.]+$", re.IGNORECASE
)

MODIFIER_INTRO = (
    "The following codelist(s) contain an ICD-10 code but none of its immediate "
    "modifier children. These modifier codes were not supported in the previous "
    "OpenCodelists ICD-10 database, but are now available for selection. If you "
    "don't include these missing codes then your codelist may miss some events. "
    "You may want to use a newer version of the codelist that includes the "
    "modifiers."
)

MODIFIER_NB = (
    "**NB: This warning is only relevant when querying the primary and secondary "
    "diagnosis fields in the APCS admissions data. If you are using the all_diagnoses "
    "field, and the contains() or contains_any_of() functions, then this is not "
    'needed as these functions "prefix match".**'
)

DEFINITION_INTRO = (
    "The following codelist(s) have codes whose description in the 2016 release "
    "of ICD-10 (used in APCS admissions data) differs from the description in the "
    "2019 release (used in ONS deaths data). If you include these codes in your "
    "codelist they may not match the events you expect depending on which data "
    "source you are targeting. You should review the codes to decide whether they "
    "are appropriate for your purposes. More instructions on how to resolve this "
    "are [available here](https://opencodelists.org/docs/#if-a-code-has-conflicting-definitions)."
)

MOVED_CODE_INTRO = (
    "The following codelist(s) have codes that have changed between the 2016 "
    "release of ICD-10 (used in APCS admissions data) and the 2019 release (used "
    "in ONS deaths data). We have found that some of the codelists in your project "
    "contain one of these codes from one release, but not the equivalent code from "
    "the other release. By not including the missing code, you may miss events "
    "depending on which data table you are targeting. You may want to use a newer "
    "version of the codelist that includes both codes."
)

X_PADDING_INTRO = (
    "The following codelist(s) contain 3 character ICD-10 codes. NHS hospital "
    "admission data pads 3 character codes with an 'X' to make them 4 characters. "
    "If you don't include the 'X' padded version of the code then your codelist may "
    "miss some events. OpenCodelists does not yet support this, but the following "
    "workaround can be added to your ehrQL code:"
)

X_PADDING_SNIPPET = """```python
# Assume we have a codelist called 'my_codelist' that contains 3 character ICD-10 codes
# This snippet will add the 'X' padded version of any 3 character codes to the codelist
my_codelist = my_codelist + [code + 'X' for code in my_codelist if len(code) == 3]
```"""

X_PADDING_NB = (
    "**NB: This workaround is only needed when querying the primary and secondary "
    "diagnosis fields in the APCS admissions data. If you are using the all_diagnoses "
    "field, and the contains() or contains_any_of() functions, then this is not "
    'needed as these functions "prefix match".**'
)


def count(warning, key):
    try:
        return int(warning[key])
    except (KeyError, TypeError, ValueError):
        return 0


def usage_total(usage_totals, code, field="apcs_all_count"):
    return usage_totals.get(code, {}).get((field, "TOTAL"), 0)


def minimal_prefixes(codes):
    """Remove codes already covered by a shorter code in the codelist."""
    return {
        code
        for code in codes
        if not any(code != other and code.startswith(other) for other in codes)
    }


def codelist_usage_total(
    usage_totals, codes, prefix_matching=False, field="apcs_all_count"
):
    """Sum APCS usage using ehrQL or Cohort Extractor matching semantics."""
    if prefix_matching:
        prefixes = minimal_prefixes(codes)
        return sum(
            usage_total(usage_totals, code, field)
            for code in usage_totals
            if any(code.startswith(prefix) for prefix in prefixes)
        )

    stored_codes = {f"{code}X" if len(code) == 3 else code for code in codes}
    return sum(usage_total(usage_totals, code, field) for code in stored_codes)


def format_ehrql_counts(primary, all_diagnoses):
    return (
        f"{primary:,} events in `primary_diagnosis` and "
        f"{all_diagnoses:,} events in `all_diagnoses`"
    )


def codelist_name(codelist_id):
    parts = codelist_id.strip("/").split("/")
    return parts[-2] if len(parts) >= 2 else codelist_id


def codelist_url(codelist_id):
    return f"https://www.opencodelists.org/codelist{codelist_id}"


def github_file_name(path):
    return Path(path).stem.replace("_", " ").replace("-", " ")


def opensafely_chapter(path):
    """Return the Roman-numeral chapter for an OpenSAFELY chapter codelist."""
    match = OPENSAFELY_CHAPTER_CODELIST_RE.fullmatch(Path(path).name)
    return match.group(1).lower() if match else None


def format_code_list(codes):
    return ", ".join(f"`{code}`" for code in sorted(codes))


def generate_repo_emails(
    all_results,
    codes,
    groups,
    usage_totals,
    prefix_warnings,
    changed_definitions=None,
    project_types=None,
    prefix_details=None,
    generated_on=None,
):
    """Generate one template-based Markdown report per affected repository."""
    del codes  # Descriptions come from the structured moved/definition inputs.
    changed_definitions = changed_definitions or {}
    project_types = project_types or {}
    prefix_details = prefix_details or {}
    generated_on = generated_on or date.today().isoformat()

    def project_type_for(repo):
        repo_name = repo.removeprefix("opensafely/")
        return (
            project_types.get(repo)
            or project_types.get(repo_name)
            or project_types.get(f"opensafely/{repo_name}")
        )

    repo_file_matches = defaultdict(lambda: defaultdict(list))
    for code, repo_results in all_results.items():
        for repo, matches in repo_results.items():
            if project_type_for(repo) == "ignore":
                continue
            for match in matches:
                chapter = opensafely_chapter(match["path"])
                if project_type_for(repo) == "cohortextractor" and chapter not in (
                    None,
                    "i",
                ):
                    continue
                if chapter == "i" and code == "A925":
                    continue
                repo_file_matches[repo][match["path"]].append(
                    {"code": code, "line": match["line_text"]}
                )

    EMAIL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in EMAIL_OUTPUT_DIR.rglob("*.md"):
        try:
            old_file.unlink()
        except OSError:
            pass

    def format_repo_report(repo, files_by_path):
        repo_name = repo.removeprefix("opensafely/")
        project_type = project_type_for(repo)
        warnings = prefix_warnings.get(repo_name, []) if project_type == "ehrql" else []

        x_warnings = [
            warning
            for warning in warnings
            if count(warning, "x_padded") > count(warning, "current")
        ]
        modifier_warnings = [
            warning
            for warning in warnings
            if count(warning, "with_prefix") > count(warning, "x_padded")
        ]

        default_branch = None
        file_cache = {}

        def get_default_branch():
            nonlocal default_branch
            if default_branch is not None:
                return default_branch
            success, output = run_gh_command(["api", f"repos/opensafely/{repo_name}"])
            default_branch = "main"
            if success and output:
                try:
                    default_branch = json.loads(output).get("default_branch") or "main"
                except json.JSONDecodeError:
                    pass
            return default_branch

        def get_file_codes(path):
            if path in file_cache:
                return file_cache[path]
            branch = get_default_branch()
            success, output = run_gh_command(
                ["api", f"repos/opensafely/{repo_name}/contents/{path}?ref={branch}"]
            )
            contents = ""
            if success and output:
                try:
                    payload = json.loads(output)
                    if payload.get("content") and payload.get("encoding") == "base64":
                        contents = base64.b64decode(payload["content"]).decode(
                            "utf-8", errors="replace"
                        )
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
            file_cache[path] = extract_icd10_codes(contents)
            return file_cache[path]

        def github_file_url(path):
            return (
                f"https://github.com/opensafely/{repo_name}/blob/"
                f"{get_default_branch()}/{path}"
            )

        changed_by_file = []
        moved_by_file = []
        prefix_matching = project_type == "cohortextractor"
        for path, matches in sorted(files_by_path.items()):
            match_codes = {match["code"] for match in matches}
            file_codes = get_file_codes(path) | match_codes
            current_usage = codelist_usage_total(
                usage_totals, file_codes, prefix_matching=prefix_matching
            )
            current_primary_usage = codelist_usage_total(
                usage_totals, file_codes, field="apcs_primary_count"
            )
            changed_code_set = match_codes & set(changed_definitions)
            changed_codes = sorted(changed_code_set)
            if changed_codes:
                changed_by_file.append(
                    {
                        "path": path,
                        "codes": changed_codes,
                        "current": current_usage,
                        "current_primary": current_primary_usage,
                        "without_changed": codelist_usage_total(
                            usage_totals,
                            file_codes - changed_code_set,
                            prefix_matching=prefix_matching,
                        ),
                        "without_changed_primary": codelist_usage_total(
                            usage_totals,
                            file_codes - changed_code_set,
                            field="apcs_primary_count",
                        ),
                    }
                )

            group_findings = []
            for group in groups:
                searched_codes = set(group.get("codes", []))
                if not searched_codes & match_codes:
                    continue
                equivalent_codes = (
                    searched_codes
                    | set(get_actual_codes(group, searched_codes))
                    | set(group.get("related_codes", []))
                )
                found_codes = equivalent_codes & file_codes
                missing_codes = equivalent_codes - found_codes
                if not missing_codes:
                    continue
                group_findings.append(
                    {
                        "description": group.get("description", "Affected codes"),
                        "found": sorted(found_codes),
                        "missing": sorted(missing_codes),
                        "current": current_usage,
                        "current_primary": current_primary_usage,
                        "would": codelist_usage_total(
                            usage_totals,
                            file_codes | missing_codes,
                            prefix_matching=prefix_matching,
                        ),
                        "would_primary": codelist_usage_total(
                            usage_totals,
                            file_codes | missing_codes,
                            field="apcs_primary_count",
                        ),
                    }
                )
            if group_findings:
                moved_by_file.append((path, group_findings))

        sections = []
        x_padding_sections = []

        if modifier_warnings:
            lines = [
                "## Action recommended: modifier codes may be missing",
                "",
                MODIFIER_INTRO,
                "",
                MODIFIER_NB,
                "",
                "Event counts in this section are 2024-25 APCS totals.",
                "",
            ]
            for warning in modifier_warnings:
                codelist = warning["codelist"]
                details = prefix_details.get(codelist, {})
                modifier_codes = details.get("modifier_codes", [])
                lines.extend(
                    [
                        f"[{codelist_name(codelist)}]({codelist_url(codelist)})",
                        "",
                        f"- Potentially missing modifier codes: {format_code_list(modifier_codes)}",
                        "- Codelist currently matches: "
                        + format_ehrql_counts(
                            count(warning, "x_padded"),
                            count(details, "with_x_padding_all"),
                        ),
                        "- Codelist would match: "
                        + format_ehrql_counts(
                            count(warning, "with_prefix"),
                            count(details, "with_prefix_matching_all"),
                        )
                        + " if missing modifier codes were included",
                        "",
                    ]
                )
            sections.append(lines)

        if changed_by_file:
            lines = [
                "## Action required: code descriptions differ",
                "",
                DEFINITION_INTRO,
                "",
                "Event counts in this section are all-years APCS totals.",
                "",
            ]
            for finding in changed_by_file:
                lines.extend(
                    [
                        f"[{github_file_name(finding['path'])}]"
                        f"({github_file_url(finding['path'])})",
                        "",
                    ]
                )
                for code in finding["codes"]:
                    definitions = changed_definitions[code]
                    lines.extend(
                        [
                            f"- **`{code}`:**",
                            f"  - NHS 2016 definition: {definitions['2016']}",
                            f"  - WHO 2019 definition: {definitions['2019']}",
                        ]
                    )
                if project_type == "ehrql":
                    current = format_ehrql_counts(
                        finding["current_primary"], finding["current"]
                    )
                    without_changed = format_ehrql_counts(
                        finding["without_changed_primary"],
                        finding["without_changed"],
                    )
                else:
                    current = f"{finding['current']:,} APCS events"
                    without_changed = f"{finding['without_changed']:,} APCS events"
                lines.extend(
                    [
                        f"- Codelist currently matches: {current}",
                        f"- Codelist would match: {without_changed} if all codes "
                        "with differing descriptions were removed",
                        "",
                    ]
                )
            sections.append(lines)

        if moved_by_file:
            lines = [
                "## Action recommended: codes may be missing",
                "",
                MOVED_CODE_INTRO,
                "",
                "Event counts in this section are all-years APCS totals.",
                "",
            ]
            for path, findings in moved_by_file:
                lines.extend(
                    [
                        f"[{github_file_name(path)}]({github_file_url(path)})",
                        "",
                    ]
                )
                for finding in findings:
                    if project_type == "ehrql":
                        current = format_ehrql_counts(
                            finding["current_primary"], finding["current"]
                        )
                        would = format_ehrql_counts(
                            finding["would_primary"], finding["would"]
                        )
                    else:
                        current = f"{finding['current']:,} APCS events"
                        would = f"{finding['would']:,} APCS events"
                    lines.extend(
                        [
                            f"- **{finding['description']}:** Equivalent codes differ between the NHS 2016 and WHO 2019 releases.",
                            "  - Codes found in this codelist: "
                            f"{format_code_list(finding['found'])}",
                            "  - Codes potentially missing from this codelist: "
                            f"{format_code_list(finding['missing'])}",
                            f"  - Codelist currently matches: {current}",
                            f"  - Codelist would match: {would} if missing codes were included",
                        ]
                    )
                lines.append("")
            sections.append(lines)

        if x_warnings:
            lines = [
                "## Action recommended: missing 'X' padded codes",
                "",
                X_PADDING_INTRO,
                "",
                "Event counts in this section are 2024-25 APCS totals.",
                "",
                X_PADDING_SNIPPET,
                "",
                X_PADDING_NB,
                "",
            ]
            for warning in x_warnings:
                codelist = warning["codelist"]
                details = prefix_details.get(codelist, {})
                x_codes = details.get("x_padded_codes", [])
                lines.extend(
                    [
                        f"[{codelist_name(codelist)}]({codelist_url(codelist)})",
                        "",
                        f"- Codes that should be 'X' padded: {format_code_list(x_codes)}",
                        "- Codelist currently matches: "
                        + format_ehrql_counts(
                            count(warning, "current"),
                            count(details, "baseline_all"),
                        ),
                        "- Codelist would match: "
                        + format_ehrql_counts(
                            count(warning, "x_padded"),
                            count(details, "with_x_padding_all"),
                        )
                        + " if 'X' padded codes were included",
                        "",
                    ]
                )
            x_padding_sections.append(lines)

        def render_report(report_sections):
            if not report_sections:
                return None

            lines = [
                "# ICD-10 codelists that require review",
                "",
                f"_Generated on {generated_on}_",
                "",
                "Following the new ICD-10 OpenSAFELY release on OpenCodelists, "
                f"we've identified that the project, [{repo_name}]"
                f"(https://github.com/opensafely/{repo_name}), is using ICD-10 "
                "codelists that should be reviewed.",
                "",
                "**This report only lists the codelists we've identified as requiring "
                "review.** It explains why each has been flagged and provides links to "
                "review the relevant codelist or source file.",
                "",
            ]
            for section in report_sections:
                lines.extend(section)
            return "\n".join(lines).rstrip() + "\n"

        return render_report(sections), render_report(x_padding_sections)

    prefix_repos = {
        repo for repo in prefix_warnings if project_type_for(repo) == "ehrql"
    }
    all_repos = set(repo_file_matches) | prefix_repos
    for repo in sorted(all_repos):
        report, x_padding_report = format_repo_report(
            repo, repo_file_matches.get(repo, {})
        )
        repo_name = repo.removeprefix("opensafely/")
        project_type = project_type_for(repo)
        reports_to_write = []
        if report is not None:
            output_dir = (
                EMAIL_OUTPUT_DIR / project_type if project_type else EMAIL_OUTPUT_DIR
            )
            reports_to_write.append((output_dir, report))
        if x_padding_report is not None:
            reports_to_write.append(
                (EMAIL_OUTPUT_DIR / "ehrql-x-padding", x_padding_report)
            )

        for output_dir, content in reports_to_write:
            output_path = output_dir / f"{repo_name}.md"
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content)
            except OSError as error:
                print(f"WARNING: Could not write report for {repo}: {error}")


def main():
    force = "--force" in sys.argv
    success, error = run_gh_command(["--version"])
    if not success:
        print(f"ERROR: Could not run gh CLI: {error}")
        print("\nInstall and authenticate the GitHub CLI with: gh auth login")
        sys.exit(1)

    moved_codes, groups = load_swapped_codes()
    changed_definitions = load_changed_code_definitions()
    if not moved_codes and not changed_definitions:
        sys.exit(1)
    codes = dict(moved_codes)
    codes.update(
        {code: definitions["2019"] for code, definitions in changed_definitions.items()}
    )

    all_results = find_all_codes_in_github(set(codes), force)
    overrides = load_project_type_overrides()
    all_results, project_types = filter_cohortextractor_moved_codes(
        all_results, groups, overrides
    )
    usage_totals, _ = load_usage_data("apcs")
    prefix_warnings = load_prefix_matching_warnings()
    prefix_details = load_prefix_matching_details()

    for repo_name in prefix_warnings:
        repo = f"opensafely/{repo_name}"
        if not project_types.get(repo):
            # This input is produced exclusively from ehrQL codelist usage.
            project_types[repo] = get_project_type(repo, overrides) or "ehrql"

    unknown_repos = sorted(
        repo.removeprefix("opensafely/")
        for repo, project_type in project_types.items()
        if project_type is None
    )
    if unknown_repos:
        print(
            "\nUncategorised repositories (add these to "
            f"{PORT_DIR / 'data' / 'project_type_overrides.json'}):"
        )
        for repo in unknown_repos:
            print(f'  "{repo}": "ehrql"')

    generate_repo_emails(
        all_results,
        codes,
        groups,
        usage_totals,
        prefix_warnings,
        changed_definitions,
        project_types,
        prefix_details,
    )


if __name__ == "__main__":
    main()
