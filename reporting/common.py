import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "reporting" / "data"
OUT_DIR = REPO_ROOT / "reporting" / "outputs"
OUTPUT_DIR = REPO_ROOT / "output"
OCL_ICD10_2019_CODES_FILE = DATA_DIR / "ocl_icd10_codes.txt"
CACHE_DIR = DATA_DIR / "codelist_cache"
USAGE_FILE_APCS = OUT_DIR / "code_usage_combined_apcs.csv"
USAGE_FILE_ONS_DEATHS = OUT_DIR / "code_usage_combined_ons_deaths.csv"
EHRQL_JSON_FILE = DATA_DIR / "ehrql_codelists.json"
RSI_JSON_FILE = DATA_DIR / "rsi-codelists-analysis.json"


def load_ocl_codes() -> set:
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

    with open(usage_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["icd10_code"]
            year = row["financial_year"]

            # Process each count column
            for col in reader.fieldnames:
                if col not in ["icd10_code", "financial_year", "in_opencodelists"]:
                    value = row[col]
                    raw_usage[code][(col, year)] = value  # Store original value

                    # Treat suppressed values like '<15' as 0
                    if value.startswith("<"):
                        count = 0
                    else:
                        count = int(value) if value else 0

                    usage[code][(col, year)] += count

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


_ehrql_data = None


def _get_ehrql_data():
    global _ehrql_data
    if _ehrql_data is None:
        if not EHRQL_JSON_FILE.exists():
            print(
                f"  WARNING: ehrql JSON file not found at {EHRQL_JSON_FILE}",
                file=sys.stderr,
            )
            return None

        try:
            with open(EHRQL_JSON_FILE) as f:
                _ehrql_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: Could not load ehrql JSON file: {e}", file=sys.stderr)
            return None
    return _ehrql_data


def extract_codelist_ids(json_path):
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
    for hash_value, files in signatures.items():
        for filename, variables in files.items():
            for variable_name, codelist_list in variables.items():
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
    codelist_ids, inline_tuples = extract_codelist_ids(EHRQL_JSON_FILE)

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
