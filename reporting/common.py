from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "reporting" / "data"
OUT_DIR = REPO_ROOT / "reporting" / "outputs"
OUTPUT_DIR = REPO_ROOT / "output"
OCL_ICD10_2019_CODES_FILE = DATA_DIR / "ocl_icd10_codes.txt"


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
