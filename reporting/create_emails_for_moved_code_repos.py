#!/usr/bin/env python3
"""
Search GitHub for ICD-10 code occurrences in opensafely org repos where the
code has moved between the version in HES and the version in OpenCodelists.

For each code in swapped_codes.json, searches all opensafely repos
and generates a markdown email report per repo with findings.

Usage:
    gh auth login  # if not already authenticated
    python reporting/create_emails_for_moved_code_repos.py [--force]

    --force: Ignore cache and fetch fresh results from GitHub
"""

import base64
import json
import sys
from collections import defaultdict

from .common import (
    REPORTING_DIR,
    find_all_codes_in_github,
    load_prefix_matching_warnings,
    load_swapped_codes,
    load_usage_data,
    run_gh_command,
)


EMAIL_OUTPUT_DIR = REPORTING_DIR / "repo_emails"


def generate_repo_emails(all_results, codes, groups, usage_totals, prefix_warnings):
    """Generate markdown emails for each repo."""

    # Aggregate all results by repo and file
    repo_file_matches = defaultdict(lambda: defaultdict(list))

    for code in all_results:
        for repo, matches in all_results[code].items():
            for match in matches:
                path = match["path"]
                line_text = match["line_text"]
                repo_file_matches[repo][path].append(
                    {
                        "code": code,
                        "line": line_text,
                        "description": codes.get(code, ""),
                    }
                )

    # Ensure per-repo email directory is fresh
    EMAIL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in EMAIL_OUTPUT_DIR.glob("*.md"):
        try:
            old_file.unlink()
        except OSError:
            pass

    def format_repo_email_section(repo_name, files_by_path):
        # Collect codes present in this repo
        repo_codes = set()
        for file_matches in files_by_path.values():
            for match in file_matches:
                repo_codes.add(match["code"])

        # Build group sections with usage
        email_lines = []
        email_lines.append(f"## opensafely/{repo_name}")
        email_lines.append("")

        # Add prefix matching warnings if present for this repo
        if repo_name in prefix_warnings:
            warnings = prefix_warnings[repo_name]
            email_lines.append("### ⚠️  Prefix Matching Warning for ehrQL Users")
            email_lines.append("")
            email_lines.append(
                "Your study uses codelist(s) that may be affected by changes in prefix matching behavior "
                "between Cohort Extractor and ehrQL."
            )
            email_lines.append("")
            email_lines.append(
                "**Background**: In Cohort Extractor (the old framework), prefix matching was applied by default when "
                "querying the primary and secondary diagnosis fields in HES APCS data. This means that "
                "a code like `E10` would automatically match `E10`, `E100`, `E101`, `E102`, etc."
            )
            email_lines.append("")
            email_lines.append(
                "**In ehrQL, prefix matching is NOT automatically applied to these fields.** "
                "If your codelist is incomplete (contains parent codes without all their descendants), "
                "you may be under-ascertaining cases."
            )
            email_lines.append("")
            email_lines.append(
                "There are two distinct issues. The first is that the HES APCS data pads any 3 character "
                "codes with an 'X' to make them 4 characters long. So C19 would appear in the data as C19X. "
                "Some users handle this in their ehrQL by manually adding 'X' padded versions of their codes "
                "to their codelists. The second issue, is that there are 5 character codes in ICD-10 that "
                "do not appear in OpenCodelists. The figures below show how many events are found when using "
                "your current codelist, how many when adding 'X' padding, and how many when using full prefix matching."
            )
            email_lines.append("")
            email_lines.append(
                "**NB: event counts are for the `primary_diagnosis` field in the HES APCS data for April 2024 to March 2025.**"
            )
            email_lines.append("")
            email_lines.append("**Affected Codelists:**")
            email_lines.append("")

            for warning in warnings:
                codelist = warning["codelist"]
                current = warning["current"]
                x_padded = warning["x_padded"]
                with_prefix = warning["with_prefix"]

                # Format numbers with commas
                try:
                    current_formatted = f"{int(current):,}"
                except ValueError:
                    current_formatted = current

                try:
                    x_padded_formatted = f"{int(x_padded):,}"
                except ValueError:
                    x_padded_formatted = x_padded

                try:
                    with_prefix_formatted = f"{int(with_prefix):,}"
                except ValueError:
                    with_prefix_formatted = with_prefix

                email_lines.append(f"- **`{codelist}`**")
                email_lines.append(f"  - Current events: {current_formatted}")
                email_lines.append(f"  - With 'X' padding: {x_padded_formatted}")
                email_lines.append(
                    f"  - With full prefix matching: {with_prefix_formatted}"
                )

            email_lines.append("")
            email_lines.append("---")
            email_lines.append("")

        # Helpers for permalinks and line numbers (scoped to this repo section)
        default_branch_cache = {}
        file_content_cache = {}

        def get_default_branch_local():
            if "branch" in default_branch_cache:
                return default_branch_cache["branch"]
            success, output = run_gh_command(["api", f"repos/opensafely/{repo_name}"])
            branch = "main"
            if success and output:
                try:
                    data = json.loads(output)
                    branch = (data.get("default_branch") or "main").strip()
                except json.JSONDecodeError:
                    pass
            default_branch_cache["branch"] = branch
            return branch

        def get_file_lines_local(path, ref):
            key = (path, ref)
            if key in file_content_cache:
                return file_content_cache[key]
            success, output = run_gh_command(
                [
                    "api",
                    f"repos/opensafely/{repo_name}/contents/{path}?ref={ref}",
                ]
            )
            lines = []
            if success and output:
                try:
                    data = json.loads(output)
                    content = data.get("content")
                    encoding = data.get("encoding")
                    if content and encoding == "base64":
                        try:
                            decoded = base64.b64decode(content).decode(
                                "utf-8", errors="replace"
                            )
                            lines = decoded.splitlines()
                        except Exception:
                            lines = []
                except json.JSONDecodeError:
                    lines = []
            file_content_cache[key] = lines
            return lines

        def find_line_numbers_local(file_lines, unique_texts):
            mapping = {}
            targets = set(unique_texts)
            for idx, line in enumerate(file_lines, start=1):
                stripped = line.strip()
                if stripped in targets and stripped not in mapping:
                    mapping[stripped] = idx
            return mapping

        # Add warning header for moved codes section if there are any groups to show
        if any(set(group.get("codes", [])) & repo_codes for group in groups):
            email_lines.append(
                "### ⚠️  Codes that moved between the 2016 and 2019 editions of ICD-10"
            )
            email_lines.append("")
            email_lines.append(
                "The following ICD-10 codes appear in your study but have been moved or changed "
                "between different editions of ICD-10. The codes you're using may not match what "
                "appears in the actual data."
            )
            email_lines.append("")

        for group in groups:
            group_codes = group.get("codes", [])
            description = group.get("description", "")
            actual_codes = group.get("actual_codes", [])
            present = sorted(set(group_codes) & repo_codes)
            if not present:
                continue
            # Header should reflect only codes present in this repo for the group
            header_codes = ", ".join(present)
            email_lines.append(f"### {header_codes} - {description}")
            email_lines.append("")
            # Compose usage phrase for actual codes
            usage_phrases = []
            for ac in actual_codes:
                entry = usage_totals.get(ac, {("apcs_all_count", "TOTAL"): 0})
                usage_phrases.append(
                    f"{ac} has occurred {entry.get(('apcs_all_count', 'TOTAL'), 0)} times"
                )
            usage_text = "; ".join(usage_phrases)

            # Singular/plural wording based on count of present codes and actual codes
            plural_present = len(present) != 1
            plural_actual = len(actual_codes) != 1
            subject = "These codes" if plural_present else "This code"
            verb_appear = "appear" if plural_present else "appears"
            verb_use = "use" if plural_present else "uses"
            actual_word = "codes" if plural_actual else "code"
            actual_codes_str = ", ".join(actual_codes)

            # Custom phrasing per code group
            is_g906 = "G906" in group_codes
            is_k58_group = any(c.startswith("K58") for c in group_codes)
            is_u_group = all(c.startswith("U") for c in group_codes)

            if is_g906:
                email_lines.append(
                    f"{subject} ({', '.join(present)}) {verb_appear} in the 2019 edition of ICD10, "
                    f"but {verb_use} the older 2016 {actual_word} ({actual_codes_str}) in HES APCS data."
                )
            elif is_k58_group:
                email_lines.append(
                    f"{subject} ({', '.join(present)}) {verb_appear} in the 2019 edition of ICD10, "
                    f"but {verb_use} the older 2016 {actual_word} ({actual_codes_str}) in HES APCS data."
                )
            elif is_u_group:
                email_lines.append(
                    f"{subject} ({', '.join(present)}) {verb_appear} in the 2019 edition of ICD10, "
                    f"and in the ONS deaths data, but {verb_use} the older 2016 {actual_word} "
                    f"({actual_codes_str}) in the HES APCS data."
                )
            else:
                appear_as = "appear" if plural_present else "appears"
                email_lines.append(
                    f"{subject} ({', '.join(present)}) {verb_appear} in the ONS deaths data, "
                    f"but {appear_as} as {actual_codes_str} in HES APCS data."
                )

            if usage_text:
                email_lines.append(f"{usage_text}.")
            email_lines.append("")

        # Then include file sections (no 'Files matching codes' line)
        for file_path in sorted(files_by_path.keys()):
            matches = files_by_path[file_path]
            email_lines.append(f"### {file_path}")
            email_lines.append("")

            # Group matches by code for clarity
            matches_by_code = defaultdict(list)
            for match in matches:
                matches_by_code[match["code"]].append(match)

            # Determine default branch and file lines for permalink generation
            branch = get_default_branch_local()
            file_lines = get_file_lines_local(file_path, branch)

            if len(matches_by_code) == 1:
                code = list(matches_by_code.keys())[0]
                code_matches = matches_by_code[code]
                description = codes.get(code, "")
                email_lines.append(f"**{code}** - {description}")
                email_lines.append("")
                # Deduplicate lines while preserving order
                seen_lines = set()
                unique_lines = []
                for match in code_matches:
                    ln = match["line"]
                    if ln not in seen_lines:
                        seen_lines.add(ln)
                        unique_lines.append(ln)
                # Print code block
                email_lines.append("```")
                for ln in unique_lines:
                    email_lines.append(ln)
                email_lines.append("```")
                # Permalinks with range collapsing
                ln_map = find_line_numbers_local(file_lines, unique_lines)
                line_numbers = [ln_map.get(ln) for ln in unique_lines]
                # Group contiguous line numbers
                ranges = []
                if line_numbers and line_numbers[0] is not None:
                    start = line_numbers[0]
                    end = start
                    for num in line_numbers[1:]:
                        if num is None:
                            break
                        if num == end + 1:
                            end = num
                        else:
                            ranges.append((start, end))
                            start = num
                            end = num
                    ranges.append((start, end))

                for start, end in ranges:
                    if start == end:
                        email_lines.append(
                            f"- Line {start}: https://github.com/opensafely/{repo_name}/blob/{branch}/{file_path}#L{start}"
                        )
                    else:
                        email_lines.append(
                            f"- Lines {start}-{end}: https://github.com/opensafely/{repo_name}/blob/{branch}/{file_path}#L{start}-L{end}"
                        )

                if not ranges:
                    email_lines.append(
                        f"- Permalink: https://github.com/opensafely/{repo_name}/blob/{branch}/{file_path}"
                    )
                email_lines.append("")
            else:
                email_lines.append("Codes:")
                email_lines.append("")
                for code in sorted(matches_by_code.keys()):
                    description = codes.get(code, "")
                    email_lines.append(f"- **{code}** - {description}")
                email_lines.append("")
                # Build unique lines across codes
                seen_lines = set()
                unique_lines = []
                for code in sorted(matches_by_code.keys()):
                    for match in matches_by_code[code]:
                        ln = match["line"]
                        if ln not in seen_lines:
                            seen_lines.add(ln)
                            unique_lines.append(ln)
                email_lines.append("```")
                for ln in unique_lines:
                    email_lines.append(ln)
                email_lines.append("```")
                # Permalinks for unique lines with range collapsing
                ln_map = find_line_numbers_local(file_lines, unique_lines)
                line_numbers = [ln_map.get(ln) for ln in unique_lines]
                # Group contiguous line numbers
                ranges = []
                if line_numbers and line_numbers[0] is not None:
                    start = line_numbers[0]
                    end = start
                    for num in line_numbers[1:]:
                        if num is None:
                            break
                        if num == end + 1:
                            end = num
                        else:
                            ranges.append((start, end))
                            start = num
                            end = num
                    ranges.append((start, end))

                for start, end in ranges:
                    if start == end:
                        email_lines.append(
                            f"- Line {start}: https://github.com/opensafely/{repo_name}/blob/{branch}/{file_path}#L{start}"
                        )
                    else:
                        email_lines.append(
                            f"- Lines {start}-{end}: https://github.com/opensafely/{repo_name}/blob/{branch}/{file_path}#L{start}-L{end}"
                        )

                if not ranges:
                    email_lines.append(
                        f"- Permalink: https://github.com/opensafely/{repo_name}/blob/{branch}/{file_path}"
                    )
                email_lines.append("")

        return "\n".join(email_lines) + "\n"

    # Collect all repos (both from code search and prefix matching warnings)
    all_repos = set(repo_file_matches.keys()) | set(prefix_warnings.keys())

    # Write results organized by repo, then by file and emit per-repo files
    for repo in sorted(all_repos):
        files = repo_file_matches.get(repo, {})

        # Write per-repo text file for emailing
        email_path = EMAIL_OUTPUT_DIR / f"{repo}.md"
        try:
            email_text = format_repo_email_section(repo, files)
            with open(email_path, "w") as email_file:
                email_file.write(email_text.strip() + "\n")
        except OSError as e:
            print(f"WARNING: Could not write email file for {repo}: {e}")


def main():
    """Main entry point."""
    # Check for --force flag
    force = "--force" in sys.argv

    # Check if gh CLI is available
    success, _ = run_gh_command(["--version"])
    if not success:
        print("ERROR: gh CLI not installed")
        print("\nSetup instructions:")
        print("1. Install gh CLI: https://cli.github.com")
        print("2. Authenticate: gh auth login")
        print("3. Run this script again")
        sys.exit(1)

    codes, groups = load_swapped_codes()
    if not codes:
        sys.exit(1)

    all_results = find_all_codes_in_github(set(codes.keys()), force)
    usage_totals, _ = load_usage_data("apcs")
    prefix_warnings = load_prefix_matching_warnings()

    if prefix_warnings:
        print(
            f"\nLoaded prefix matching warnings for {len(prefix_warnings)} repositories"
        )

    generate_repo_emails(all_results, codes, groups, usage_totals, prefix_warnings)


if __name__ == "__main__":
    main()
