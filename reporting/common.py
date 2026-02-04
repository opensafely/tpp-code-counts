import csv
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).parent.parent
REPORTING_DIR = REPO_ROOT / "reporting"
DATA_DIR = REPORTING_DIR / "data"
OUT_DIR = REPORTING_DIR / "outputs"
OUTPUT_DIR = REPO_ROOT / "output"
OCL_ICD10_2019_CODES_FILE = DATA_DIR / "ocl_icd10_codes.txt"
CACHE_DIR = DATA_DIR / "codelist_cache"
USAGE_FILE_APCS = OUT_DIR / "code_usage_combined_apcs.csv"
USAGE_FILE_ONS_DEATHS = OUT_DIR / "code_usage_combined_ons_deaths.csv"
EHRQL_JSON_FILE = DATA_DIR / "ehrql_codelists.json"
RSI_JSON_FILE = DATA_DIR / "rsi-codelists-analysis.json"
COVERAGE_APCS_FILE = OUT_DIR / "codelist_coverage_detail_apcs.csv"
COVERAGE_ONS_DEATHS_FILE = OUT_DIR / "codelist_coverage_detail_ons_deaths.csv"
REPOS_OUTPUT_FILE = OUT_DIR / "prefix_matching_repos.csv"
GITHUB_CACHE_FILE = DATA_DIR / "github_code_search_cache.json"
SWAPPED_CODES_FILE = REPORTING_DIR / "swapped_codes.json"


def load_ocl_codes() -> dict[str, set[str]]:
    """Load all ICD10 codes from OpenCodelists export.
    ONS death data is always 3 and 4 character ICD10 codes, while apcs
    pads 3 character codes without children with an X to make 4 character codes.
    """
    ocl_codes = {
        "apcs": set(),
        "ons_deaths": set(),
    }
    with open(OCL_ICD10_2019_CODES_FILE) as f:
        for line in f:
            code = line.strip()
            if code and "-" not in code:  # ocl contains code ranges which we'll ignore
                ocl_codes["ons_deaths"].add(code)
    # Should be at least 12,000
    assert len(ocl_codes["ons_deaths"]) >= 12000, "Loaded too few ICD10 codes from OCL"

    # Should contain some known codes
    for known_code in ["A00", "B99", "C341", "E119", "I10", "J459", "Z992"]:
        assert known_code in ocl_codes["ons_deaths"], (
            f"Known ICD10 code {known_code} missing from OCL codes"
        )

    # Now we create the APCS OCL codes set by adding 4-char codes with X suffixes
    for code in ocl_codes["ons_deaths"]:
        if len(code) != 3:
            ocl_codes["apcs"].add(code)
        else:
            # Check if this 3-char code has any children in OCL
            has_children = any(
                other_code.startswith(code) and len(other_code) > 3
                for other_code in ocl_codes["ons_deaths"]
            )
            if not has_children:
                # Add the 4-char code with X suffix
                ocl_codes["apcs"].add(f"{code}X")
    return ocl_codes


_rsi_data = None


def _get_rsi_data():
    global _rsi_data
    if _rsi_data is None:
        if not RSI_JSON_FILE.exists():
            print(
                f"  WARNING: RSI codelists file not found at {RSI_JSON_FILE}",
                file=sys.stderr,
            )
            return None

        try:
            with open(RSI_JSON_FILE) as f:
                _rsi_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: Could not load RSI codelists: {e}", file=sys.stderr)
            return None
    return _rsi_data


def load_rsi_codelists():
    """
    Load all the codelists from OpenCodelists (from the RSI export from previous work).
    Returns a mapping of version slugs and hashes to coding system and creation method.
    """
    data = _get_rsi_data()
    if data is None:
        return {}

    # Build a mapping: version_slug or hash-> (coding_system, full_entry)
    # Each codelist can have multiple versions
    codelist_map = {}

    for entry in data:
        coding_system = entry.get("coding_system", "")
        base_slug = entry.get("slug", "")
        versions = entry.get("versions", [])

        for version in versions:
            tag = version.get("tag")
            hash_val = version.get("hash")

            metadata = {
                "coding_system": coding_system,
                "creation_method": version.get("creation_method", ""),
            }

            # Create entries for both tag and hash based slugs
            if tag:
                tag_slug = f"/{base_slug}/{tag}/"
                codelist_map[tag_slug] = metadata

            if hash_val:
                assert hash_val not in codelist_map, f"Duplicate hash {hash_val}"
                codelist_map[hash_val] = metadata

    return codelist_map


def load_all_icd10_codelists_from_rsi():
    """Load ALL ICD-10 codelist versions from the RSI export.

    This includes all public codelists (bristol, opensafely, ihme, etc.) AND
    881 user/* codelists that are not available in the OpenCodelists API.

    Returns:
        List of codelist_ids (full version slug format)
    """
    data = _get_rsi_data()
    if data is None:
        return []

    all_versions = []
    for item in data:
        if item.get("coding_system") == "icd10":
            for version in item.get("versions", []):
                version_slug = version.get("slug")
                if version_slug:
                    # Add leading and trailing slashes to match EHRQL format
                    # RSI has: user/name/hash -> we need: /user/name/hash/
                    normalized_slug = "/" + version_slug + "/"
                    all_versions.append(normalized_slug)

    print(
        f"  Found {len(all_versions)} ICD-10 codelist versions in RSI data",
        file=sys.stderr,
    )
    return all_versions


def load_usage_data(data_source):
    """Load code usage data from CSV for a specific data source.

    Args:
        data_source: Either 'apcs' or 'ons_deaths'

    Returns: tuple of (usage, raw_usage)
    - usage: dict of {code: {(category, year): count}} with processed values
    - raw_usage: dict of {code: {(category, year): raw_value}} with original string values
    where category is like 'apcs_primary_count', 'ons_contributing_count', etc.
    """
    usage_file = USAGE_FILE_APCS if data_source == "apcs" else USAGE_FILE_ONS_DEATHS
    usage = defaultdict(lambda: defaultdict(int))
    raw_usage = defaultdict(lambda: defaultdict(str))

    columns = (
        ["apcs_primary_count", "apcs_secondary_count", "apcs_all_count"]
        if data_source == "apcs"
        else [
            "ons_primary_count",
            "ons_contributing_count",
        ]
    )

    with open(usage_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["icd10_code"]
            year = row["financial_year"]

            if not code:
                continue

            for column in columns:
                count_str = row.get(column, "")
                count = parse_value(count_str)
                raw_usage[code][(column, year)] = count_str
                usage[code][(column, year)] += count

                if (column, "TOTAL") not in usage[code]:
                    usage[code][(column, "TOTAL")] = count
                else:
                    usage[code][(column, "TOTAL")] += count

    return usage, raw_usage


def download_codelist(codelist_id):
    """
    Download a codelist from OpenCodelists and return the list of codes.

    Args:
        codelist_id: The codelist ID (e.g., "/opensafely/asthma/2024-05-01/")

    Returns:
        List of codes from the "code" column, or None if download failed
    """
    # Create cache filename from codelist_id (replace slashes with underscores)
    cache_filename = codelist_id.strip("/").replace("/", "_") + ".csv"
    cache_path = CACHE_DIR / cache_filename

    # Download from OpenCodelists
    url = f"https://www.opencodelists.org/codelist{codelist_id}download.csv"

    try:
        # Create request with a user agent to be polite
        request = Request(url, headers={"User-Agent": "opensafely/tpp-code-counts/1.0"})

        with urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8")

            # Save to cache
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(content)
    except HTTPError as e:
        print(f"  WARNING: HTTP {e.code} for {codelist_id}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"  WARNING: URL error for {codelist_id}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  WARNING: Error downloading {codelist_id}: {e}", file=sys.stderr)
        return None


def parse_codelist(filename):
    cache_path = CACHE_DIR / filename
    codes = set()
    try:
        with open(cache_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            code_col = find_code_column(reader.fieldnames)
            if code_col is None:
                return None

            for row in reader:
                code = row.get(code_col, "").strip()
                if code:
                    codes.add(code)
    except Exception as e:
        print(f"Error loading {filename}: {e}", file=sys.stderr)
        return None
    return codes


def load_codelist(codelist_id):
    """Load codes from a cached codelist CSV - or from download if not exists

    Args:
        codelist_id: The codelist ID (string)
        download: Force re-download
        inline_codes: If provided and codelist_id starts with '<inline>', use these codes

    Returns:
        Set of codes, or None if loading failed
    """

    cache_filename = codelist_id.strip("/").replace("/", "_") + ".csv"
    cache_path = CACHE_DIR / cache_filename

    # if cached file not exists OR if download is True
    if not cache_path.exists():
        # Download and cache the codelist
        download_codelist(codelist_id)

    return parse_codelist(cache_filename)


def find_code_column(fieldnames):
    """Find the column name that contains the codes."""
    for candidate in ["code", "icd10_code", "icd", "ICD_code"]:
        if candidate in fieldnames:
            return candidate

    # Try case-insensitive
    lower_fields = {name.lower(): name for name in fieldnames}
    for candidate in ["code", "icd10_code", "icd", "icd_code"]:
        if candidate in lower_fields:
            return lower_fields[candidate]

    return None


_ehrql_data: dict = {}


def _get_ehrql_data() -> dict:
    global _ehrql_data
    if not _ehrql_data:
        if not EHRQL_JSON_FILE.exists():
            print(
                f"  WARNING: ehrql JSON file not found at {EHRQL_JSON_FILE}",
                file=sys.stderr,
            )
            return {}

        try:
            with open(EHRQL_JSON_FILE) as f:
                _ehrql_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: Could not load ehrql JSON file: {e}", file=sys.stderr)
            return {}
    return _ehrql_data


def extract_codelist_ids():
    """Extract all unique codelist IDs from the signatures structure.

    Returns:
        Tuple of (codelist_ids, inline_codelists) where inline_codelists is a list of
        tuples (sorted_codes,) that uniquely identify each inline codelist.
    """
    data = _get_ehrql_data()

    codelist_ids = set()
    inline_codelists = set()

    # Navigate: signatures > hash > filename > variable_name > list of lists
    signatures = data.get("signatures", {})
    for _, files in signatures.items():
        for _, variables in files.items():
            for _, codelist_list in variables.items():
                # codelist_list is a list of entries, each entry is [codelist_id, ...]
                for entry in codelist_list:
                    if entry and len(entry) > 0:
                        # First element of each entry is the codelist ID
                        codelist_id = entry[0]
                        if codelist_id:
                            if codelist_id == "<inline>":
                                # For inline, extract codes from 4th element (index 3)
                                # Should be "values={pipe separated list}"
                                values_str = entry[3]
                                codes = values_str[7:]  # Remove "values=" prefix
                                # Split by pipe, sort, and create normalized representation
                                code_list = [c.strip() for c in codes.split("|")]
                                # Use sorted tuple as hashable unique identifier
                                normalized = tuple(sorted(code_list))
                                inline_codelists.add(normalized)
                            else:
                                codelist_ids.add(codelist_id)

    return sorted(codelist_ids), sorted(inline_codelists)


def load_icd10_codelists(rsi_map):
    """Load the list of ICD-10 codelist IDs from the ehrql extraction logic.

    Returns:
        Tuple of (codelist_ids, inline_codelists) where inline_codelists are dicts with
        'id' (synthetic ID) and 'codes' (set of codes).
    """
    # Extract codelist IDs from ehrql file
    codelist_ids, inline_tuples = extract_codelist_ids()

    # Filter named codelists for ICD-10 only
    icd10_codelists = []
    for codelist_id in codelist_ids:
        if codelist_id in rsi_map:
            coding_system = rsi_map[codelist_id]["coding_system"].lower()
            if coding_system == "icd10":
                icd10_codelists.append(codelist_id)
        else:
            # Try hash-only match
            parts = codelist_id.strip("/").split("/")
            if parts:
                last_part = parts[-1]
                if last_part in rsi_map:
                    coding_system = rsi_map[last_part]["coding_system"].lower()
                    if coding_system == "icd10":
                        icd10_codelists.append(codelist_id)
                else:
                    print(
                        f"  WARNING: Codelist {codelist_id} not found in RSI metadata",
                        file=sys.stderr,
                    )

    # Process inline codelists - filter for ICD-10 codes only
    inline_codelists = []
    for code_tuple in inline_tuples:
        # Check if all codes match ICD-10 format
        if all(is_icd10_code(code) for code in code_tuple):
            # Create a synthetic ID for this inline codelist using a hash
            # This keeps the ID short and filesystem-friendly
            codes_str = "|".join(code_tuple)
            code_hash = hashlib.md5(codes_str.encode()).hexdigest()[:8]
            inline_id = f"<inline>:{code_hash}"
            inline_codelists.append(
                {
                    "id": inline_id,
                    "codes": set(code_tuple),
                    "codes_str": codes_str,  # Keep full description for reporting
                }
            )
        else:
            print(
                f"  WARNING: Inline codelist with non-ICD10 codes skipped: {code_tuple}",
                file=sys.stderr,
            )

    return sorted(icd10_codelists), inline_codelists


def is_icd10_code(code):
    """Check if a code matches ICD-10 format.

    ICD-10 format: Capital letter, followed by 2-4 digits, optionally with 'X' as 4th character.
    Examples: E10, E110, E1101, E10X, M907, S92X, S92X0
    """
    # Pattern: Capital letter, then 2-4 characters that are digits or X
    # But X should only appear as the 4th character (position 3)
    pattern = r"^[A-Z]\d{2}[0-9X]?[0-9]?$"
    return bool(re.match(pattern, code))


def load_ehrql_codelists_to_repos():
    """Load ehrql_codelists.json and map codelists to repos that use them.

    Returns:
        Dict of {codelist_id: set(repos)}
    """
    data = _get_ehrql_data()

    # First, build a mapping of file_hash -> set of repos that use it
    # projects[repo][commit] = file_hash
    file_hash_to_repos = defaultdict(set)
    projects = data.get("projects", {})
    for repo_name, commit_dict in projects.items():
        if isinstance(commit_dict, dict):
            for _, file_hash in commit_dict.items():
                file_hash_to_repos[file_hash].add(repo_name)

    # Build mapping: codelist_id -> set of repos
    codelist_to_repos = defaultdict(set)

    # Navigate signatures structure: hash -> filename -> variable -> codelist_list
    signatures = data.get("signatures", {})
    for file_hash, files in signatures.items():
        # Get repos that use this file hash
        repos_for_hash = file_hash_to_repos.get(file_hash, set())

        for _, variables in files.items():
            for _, codelist_list in variables.items():
                # codelist_list is a list of entries, each starting with codelist_id
                for entry in codelist_list:
                    if entry and len(entry) > 0:
                        codelist_id = entry[0]
                        if codelist_id and codelist_id != "<inline>":
                            # Add all repos that use this file hash
                            codelist_to_repos[codelist_id].update(repos_for_hash)

    return codelist_to_repos


def get_output_file(data_source):
    """Get the coverage output file path for a given data source."""
    if data_source == "apcs":
        return COVERAGE_APCS_FILE
    elif data_source == "ons_deaths":
        return COVERAGE_ONS_DEATHS_FILE
    else:
        raise ValueError(f"Unknown data source: {data_source}")


def parse_value(value):
    """Parse a count value, treating suppressed values like '<15' as 0."""
    if value.startswith("<"):
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


_coverage_data = []
_codelist_codes = defaultdict(list)


def get_apcs_coverage_data():
    """Load the codelist coverage detail CSV."""
    global _coverage_data, _codelist_codes
    if len(_coverage_data) > 0 and _codelist_codes:
        return _coverage_data, _codelist_codes

    _coverage_data = []
    _codelist_codes = defaultdict(list)
    with open(COVERAGE_APCS_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Exists in ehrQL repo") != "Y":
                continue
            _coverage_data.append(row)
            codelist_id = row.get("codelist_id", "").strip()
            icd10_code = row.get("icd10_code", "").strip()
            status = row.get("status", "").strip()
            if not codelist_id or not icd10_code:
                continue

            # Only include codes that are in the codelist (COMPLETE, PARTIAL, NONE)
            # Skip EXTRA codes as they're not part of the original codelist
            if status in ("COMPLETE", "PARTIAL", "NONE"):
                _codelist_codes[codelist_id].append(icd10_code)
    return _coverage_data, _codelist_codes


def load_cache():
    """Load cached search results.

    Returns:
        dict: {code: {repo: [matches]}}
    """
    if not GITHUB_CACHE_FILE.exists():
        return {}

    try:
        with open(GITHUB_CACHE_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    """Save search results to cache.

    Args:
        cache: dict of {code: {repo: [matches]}}
    """
    try:
        with open(GITHUB_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
        print(f"\nCache saved to {GITHUB_CACHE_FILE}")
    except OSError as e:
        print(f"WARNING: Could not save cache: {e}")


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


def find_all_codes_in_github(codes: set[str], force: bool):
    # Check if gh CLI is available
    success, _ = run_gh_command(["--version"])
    if not success:
        print("ERROR: gh CLI not installed")
        print("\nSetup instructions:")
        print("1. Install gh CLI: https://cli.github.com")
        print("2. Authenticate: gh auth login")
        print("3. Run this script again")
        sys.exit(1)

    cache = {} if force else load_cache()
    if cache:
        print(f"Loaded {len(cache)} cached results (pass force=True to refresh)\n")

    all_results = {}

    codes_to_search = codes - set(cache.keys())
    if codes_to_search:
        print(f"Searching GitHub for {len(codes_to_search)} codes...\n")
        for i, code in enumerate(codes_to_search):
            all_results[code] = search_code_in_org(code)
            # Add delay between searches to avoid rate limiting
            if i < len(codes_to_search) - 1:
                time.sleep(2)

        # Save updated cache
        save_cache(all_results)

    return all_results


def load_prefix_matching_warnings():
    """Load prefix matching warnings per repo from prefix_matching_repos.csv.

    Returns:
        dict: {repo: [{"codelist": str, "current": int, "with_prefix": int}]}
    """
    warnings = defaultdict(list)

    if not REPOS_OUTPUT_FILE.exists():
        print(
            f"INFO: Prefix matching file not found at {REPOS_OUTPUT_FILE}, skipping prefix matching warnings"
        )
        return warnings

    try:
        with open(REPOS_OUTPUT_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                repo = row.get("repo", "").strip()
                codelist = row.get("codelist", "").strip()
                current = row.get("current_event_count", "0").strip()
                with_prefix = row.get("event_count_with_prefix_matching", "0").strip()

                # Skip repos marked as not found
                if repo == "(not found in repos)" or not repo:
                    continue

                # Remove opensafely/ prefix if present
                if repo.startswith("opensafely/"):
                    repo = repo.replace("opensafely/", "")

                # Parse numbers for filtering
                try:
                    current_num = int(current)
                    with_prefix_num = int(with_prefix)
                except ValueError:
                    current_num = 0
                    with_prefix_num = 0

                warnings[repo].append(
                    {
                        "codelist": codelist,
                        "current": current_num,
                        "with_prefix": with_prefix_num,
                        "current_str": current,
                        "with_prefix_str": with_prefix,
                    }
                )
    except OSError as e:
        print(f"WARNING: Could not read prefix matching file {REPOS_OUTPUT_FILE}: {e}")

    return warnings


def load_swapped_codes():
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
