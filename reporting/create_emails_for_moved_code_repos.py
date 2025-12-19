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
import csv
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path


# try:
#     import requests
# except ImportError:
#     print("ERROR: requests library not found. Install it: pip install requests")
#     sys.exit(1)

SWAPPED_CODES_FILE = Path(__file__).parent / "swapped_codes.json"
OUTPUT_FILE = Path(__file__).parent / "github_code_search_report.md"
EMAIL_OUTPUT_DIR = Path(__file__).parent / "repo_emails"
CACHE_FILE = Path(__file__).parent / "github_code_search_cache.json"
USAGE_FILE = Path(__file__).parent / "outputs" / "code_usage_combined_apcs.csv"
GITHUB_API = "https://api.github.com"


def run_gh_command(args):
    """Run gh CLI command and return output.

    Args:
        args: List of arguments to pass to gh

    Returns:
        tuple: (success, output) where success is bool and output is str
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check for rate limit in stderr
        if "API rate limit exceeded" in result.stderr:
            print(
                "\n⚠️  GitHub API rate limit exceeded. Waiting 60 seconds before retry..."
            )
            time.sleep(60)
            # Retry once after waiting
            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                timeout=30,
            )

        return result.returncode == 0, result.stdout.strip()
    except FileNotFoundError:
        print("ERROR: gh CLI not found. Please install it: https://cli.github.com")
        return False, ""
    except subprocess.TimeoutExpired:
        return False, ""


def load_cache():
    """Load cached search results.

    Returns:
        dict: {code: {repo: [matches]}}
    """
    if not CACHE_FILE.exists():
        return {}

    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    """Save search results to cache.

    Args:
        cache: dict of {code: {repo: [matches]}}
    """
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except OSError as e:
        print(f"WARNING: Could not save cache: {e}")


def load_usage_totals():
    """Load usage totals per ICD10 code from code_usage_combined_apcs.csv.

    Returns:
        dict: {code: {"total": int}}
    """
    totals = {}
    if not USAGE_FILE.exists():
        print(f"WARNING: Usage file not found: {USAGE_FILE}")
        return totals

    try:
        with open(USAGE_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get("icd10_code") or "").strip().upper()
                value = (row.get("apcs_all_count") or "").strip()
                if not code:
                    continue

                # Convert counts: numbers as ints; suppressed counts (<15) treated as 0
                try:
                    count = int(value)
                except ValueError:
                    count = 0

                entry = totals.setdefault(code, {"total": 0})
                entry["total"] += count
    except OSError as e:
        print(f"WARNING: Could not read usage file {USAGE_FILE}: {e}")

    return totals


def should_exclude_line(line, path):
    """Check if a line should be excluded based on filtering rules.

    Args:
        line: The line of code to check
        path: The file path

    Returns:
        bool: True if the line should be excluded, False otherwise
    """
    # Rule 1: Exclude if line contains "U12 small nuclear mutation"
    if "U12 small nuclear mutation" in line:
        return True

    # Rule 2: Exclude if line starts with "U***,Unspecified diagnostic imaging"
    # where * is a numeric character
    if re.match(r"^U\d\d\d,Unspecified diagnostic imaging", line):
        return True

    # Rule 3: Exclude if filename contains "opcs" (case-insensitive)
    if "opcs" in path.lower():
        return True

    # Rule 4: Exclude if code line is like "K58*,Percutaneous"
    if re.match(r"^K58\d,Percutaneous", line):
        return True

    # Rule 5: Exclude U10 - Falls as that is CTV3, not ICD10
    if re.match(r"^U10.*Falls", line):
        return True

    # Rule 6: Exclude K588 - Other specified diagnostic transluminal operations
    if re.match(r"^K588,Other specified diagnostic transluminal operations", line):
        return True

    return False


def search_code_in_org(code):
    """Search for a code in all opensafely repos with a single API call.

    Args:
        code: ICD-10 code to search for

    Returns:
        dict: {repo_name: [matching_lines]}
    """
    results = defaultdict(list)

    print(f"  Searching for {code}...", end="", flush=True)

    # Construct the query: "CODE" org:opensafely
    query = f'"{code}"+org:opensafely'

    success, output = run_gh_command(
        [
            "api",
            "-H",
            "Accept: application/vnd.github.text-match+json",
            f"/search/code?q={query}",
        ]
    )

    if not success:
        print(" ERROR: API call failed")
        return results

    if success and output:
        try:
            data = json.loads(output)

            # Check for rate limit error
            if "message" in data and "rate limit" in data["message"].lower():
                print(" RATE LIMITED")
                return results

            items = data.get("items", [])

            for item in items:
                path = item.get("path", "")
                repo_full_name = item.get("repository", {}).get("full_name", "")

                # Extract line text from text_matches
                line_texts = []
                text_matches = item.get("text_matches", [])
                if text_matches:
                    for match in text_matches:
                        fragment = match.get("fragment", "")
                        if fragment:
                            # Split fragment into lines and find lines containing the code
                            lines = fragment.split("\n")
                            for line in lines:
                                # Check if this line contains the exact code we're searching for
                                # Look for the code as a distinct word (capital letters/numbers)
                                if re.search(r"\b" + re.escape(code) + r"\b", line):
                                    # Strip whitespace and only add if not empty
                                    clean_line = line.strip()
                                    if clean_line:
                                        # Apply filtering rules to exclude false positives
                                        if should_exclude_line(clean_line, path):
                                            continue
                                        line_texts.append(clean_line)

                # If no matching lines found, skip this match
                if not line_texts:
                    continue

                # Extract just the repo name from opensafely/repo-name format
                if repo_full_name.startswith("opensafely/"):
                    repo = repo_full_name.replace("opensafely/", "")
                else:
                    repo = repo_full_name

                if path and repo:
                    # Remove duplicates while preserving order
                    seen = set()
                    for line_text in line_texts:
                        if line_text not in seen:
                            seen.add(line_text)
                            results[repo].append(
                                {
                                    "path": path,
                                    "line_text": line_text,
                                }
                            )
        except json.JSONDecodeError:
            pass

    found_count = len(results)
    if found_count > 0:
        total_matches = sum(len(matches) for matches in results.values())
        print(f" found in {found_count} repo(s) ({total_matches} matches)")
    else:
        print(" (no results)")

    # Convert defaultdict to regular dict for JSON serialization
    return dict(results)


def load_codes():
    """Load codes from swapped_codes.json.

    Returns:
        tuple: (codes_dict, groups_list)
            codes_dict: {code: description, ...}
            groups_list: [{"codes": [...], "description": "..."}, ...]
    """
    if not SWAPPED_CODES_FILE.exists():
        print(f"ERROR: {SWAPPED_CODES_FILE} not found")
        return {}, []

    try:
        with open(SWAPPED_CODES_FILE) as f:
            data = json.load(f)

        codes = {}
        # Expected format: [{"codes": [...], "description": "..."}, ...]
        for entry in data:
            description = entry.get("description", "")
            for code in entry.get("codes", []):
                codes[code] = description

        print(f"Loaded {len(codes)} unique codes from swapped_codes.json\n")
        return codes, data
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR loading codes: {e}")
        return {}, []


def generate_repo_emails(all_results, codes, groups, usage_totals):
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
                entry = usage_totals.get(ac, {"total": 0})
                usage_phrases.append(f"{ac} has occurred {entry.get('total', 0)} times")
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

    # Write results organized by repo, then by file and emit per-repo files
    for repo in sorted(repo_file_matches.keys()):
        files = repo_file_matches[repo]

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
    success, output = run_gh_command(["--version"])
    if not success:
        print("ERROR: gh CLI not installed")
        print("\nSetup instructions:")
        print("1. Install gh CLI: https://cli.github.com")
        print("2. Authenticate: gh auth login")
        print("3. Run this script again")
        sys.exit(1)

    codes, groups = load_codes()
    if not codes:
        sys.exit(1)

    # Load cache
    cache = {} if force else load_cache()
    if cache and not force:
        print(f"Loaded {len(cache)} cached results (use --force to refresh)\n")

    print(f"Searching opensafely org for {len(codes)} codes...\n")

    all_results = {}
    codes_to_search = []

    # Check which codes need to be searched
    for code in sorted(codes.keys()):
        if code in cache and not force:
            all_results[code] = cache[code]
            print(f"  {code}: using cached results")
        else:
            codes_to_search.append(code)

    # Search for codes not in cache
    if codes_to_search:
        print(f"\nFetching {len(codes_to_search)} code(s) from GitHub...\n")
        for i, code in enumerate(codes_to_search):
            all_results[code] = search_code_in_org(code)
            # Add delay between searches to avoid rate limiting
            if i < len(codes_to_search) - 1:
                time.sleep(2)

        # Save updated cache
        save_cache(all_results)
        print(f"\nCache saved to {CACHE_FILE}")

    usage_totals = load_usage_totals()

    generate_repo_emails(all_results, codes, groups, usage_totals)


if __name__ == "__main__":
    main()
