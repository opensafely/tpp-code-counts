import csv
import urllib.error
from pathlib import Path

import reporting.missing_codes as mc


def write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in rows:
            writer.writerow(r)


def test_missing_codes_uses_local_fallback_and_writes_reports(tmp_path, monkeypatch):
    # Prepare temporary output dir with APCS and ONS CSVs
    tmp_output = tmp_path / "output"
    apcs_file = tmp_output / "icd10_apcs_2024_25.csv"
    ons_file = tmp_output / "icd10_ons_deaths_2024_25.csv"

    # APCS contains one known OCL code and one missing code
    write_csv(
        apcs_file,
        ["icd10_code", "primary_count", "secondary_count", "all_count"],
        [["E119", "30", "<15", "40"], ["ABC999", "1", "0", "1"]],
    )

    # ONS contains no extra codes for simplicity
    write_csv(
        ons_file,
        ["icd10_code", "primary_cause_count", "contributing_cause_count"],
        [["E119", "0", "0"]],
    )

    # Monkeypatch module paths to use our tmp locations
    monkeypatch.setattr(mc, "LOCAL_USAGE_OUTPUT_DIR", tmp_output)
    monkeypatch.setattr(mc, "OUT_DIR", tmp_path / "reporting_outputs")
    # Point LOCAL_DATA_ZIP to a non-existent file to force fallback
    monkeypatch.setattr(mc, "LOCAL_DATA_ZIP", tmp_path / "nonexistent.zip")
    # Avoid calling the real load_ocl_codes (it asserts large file contents).
    # Now returns dict with apcs and ons_deaths keys
    monkeypatch.setattr(
        mc,
        "load_ocl_codes",
        lambda: {
            "apcs": {"E119", "E119X", "ZZ99", "ZZ99X"},
            "ons_deaths": {"E119", "ZZ99"},
        },
    )

    # Force remote download to fail
    def fake_urlopen(*args, **kwargs):
        raise urllib.error.URLError("no remote")

    monkeypatch.setattr(mc.urllib.request, "urlopen", fake_urlopen)

    # Run main to generate outputs
    mc.main()

    # Check outputs - now split by apcs/ons_deaths
    out_dir = tmp_path / "reporting_outputs"
    assert (out_dir / "unused_codes_apcs.csv").exists()
    assert (out_dir / "unused_codes_ons_deaths.csv").exists()
    assert (out_dir / "code_usage_combined_apcs.csv").exists()
    assert (out_dir / "code_usage_combined_ons_deaths.csv").exists()

    # Check that warning indicates local fallback
    unused_csv_text = (out_dir / "unused_codes_apcs.csv").read_text()
    assert "Remote ZIP unavailable" in unused_csv_text

    # Check that ABC999 appears in code_usage_combined_apcs.csv with in_opencodelists=no
    usage_csv_text = (out_dir / "code_usage_combined_apcs.csv").read_text()
    assert "ABC999" in usage_csv_text
    # Verify it's marked as not in OCL
    lines = usage_csv_text.strip().split("\n")
    abc_line = [l for l in lines if "ABC999" in l][0]
    assert ",no" in abc_line  # in_opencodelists column should be "no"


def test_load_code_usage_data_dev_remote_success(tmp_path, monkeypatch):
    # Create an in-memory zip with top-level CSVs and monkeypatch urlopen to return it
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # create apcs csv with partition suffix
        z.writestr(
            "icd10_apcs_2024_25_0001_4990.csv",
            "icd10_code,primary_count,secondary_count,all_count\nE119,30,<15,40\n",
        )
        z.writestr(
            "icd10_apcs_2024_25_4991_9980.csv",
            "icd10_code,primary_count,secondary_count,all_count\nE120,30,<15,40\n",
        )
        z.writestr(
            "icd10_apcs_2024_25_9981_14970.csv",
            "icd10_code,primary_count,secondary_count,all_count\nABC999,30,<15,40\n",
        )
        # create ons csv with a different partition suffix
        z.writestr(
            "icd10_ons_deaths_2024_25_4991_9980.csv",
            "icd10_code,primary_cause_count,contributing_cause_count\nABC999,1,0\n",
        )
    buf.seek(0)

    class FakeResp:
        def __init__(self, data):
            self._buf = data

        def read(self):
            return self._buf.getvalue()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(*args, **kwargs):
        return FakeResp(buf)

    monkeypatch.setattr(mc.urllib.request, "urlopen", fake_urlopen)

    reported, _ = mc.load_code_usage_data()

    print(reported)
    # Now returns dict with apcs and ons_deaths keys
    # E119 present with apcs counts
    assert "E119" in reported["apcs"]
    assert "2024-25" in reported["apcs"]["E119"]
    assert reported["apcs"]["E119"]["2024-25"]["apcs_primary_count"] == "30"
    # E120 present with apcs counts
    assert "E120" in reported["apcs"]
    assert "2024-25" in reported["apcs"]["E120"]
    assert reported["apcs"]["E120"]["2024-25"]["apcs_primary_count"] == "30"
    # ABC999 present in both apcs and ons_deaths
    assert "ABC999" in reported["apcs"]
    assert "ABC999" in reported["ons_deaths"]
    assert reported["ons_deaths"]["ABC999"]["2024-25"]["ons_primary_count"] == "1"
    assert reported["apcs"]["ABC999"]["2024-25"]["apcs_primary_count"] == "30"
    assert reported["apcs"]["ABC999"]["2024-25"]["apcs_secondary_count"] == "<15"
    assert reported["apcs"]["ABC999"]["2024-25"]["apcs_all_count"] == "40"


def test_three_char_code_with_no_children_matches_four_char_usage(
    tmp_path, monkeypatch
):
    """Test that a 3-character ICD10 code with no children in OCL matches 4-character codes in usage.

    E.g., if OCL has "A33" (3 chars) with no children like "A330", "A331", etc.,
    then "A33X" from usage data should be considered as usage of "A33".
    """
    # Prepare temporary output dir with APCS CSV
    tmp_output = tmp_path / "output"
    apcs_file = tmp_output / "icd10_apcs_2024_25.csv"

    # APCS contains A33X code (4 chars ending in X)
    write_csv(
        apcs_file,
        ["icd10_code", "primary_count", "secondary_count", "all_count"],
        [["A33X", "5", "3", "8"]],
    )

    # Monkeypatch module paths to use our tmp locations
    monkeypatch.setattr(mc, "LOCAL_USAGE_OUTPUT_DIR", tmp_output)
    monkeypatch.setattr(mc, "OUT_DIR", tmp_path / "reporting_outputs")
    # Point LOCAL_DATA_ZIP to a non-existent file to force fallback
    monkeypatch.setattr(mc, "LOCAL_DATA_ZIP", tmp_path / "nonexistent.zip")
    # OCL has A33 (3 chars) with no children, which generates A33X in apcs codes
    monkeypatch.setattr(
        mc,
        "load_ocl_codes",
        lambda: {"apcs": {"A33X"}, "ons_deaths": {"A33"}},
    )

    # Force remote download to fail
    def fake_urlopen(*args, **kwargs):
        raise urllib.error.URLError("no remote")

    monkeypatch.setattr(mc.urllib.request, "urlopen", fake_urlopen)

    # Run main to generate outputs
    mc.main()

    # Check that A33X appears in code_usage_combined_apcs.csv with in_opencodelists=yes
    # (because A33X is now in OCL as the 4-char version of 3-char A33)
    apcs_usage_file = tmp_path / "reporting_outputs" / "code_usage_combined_apcs.csv"
    with open(apcs_usage_file) as f:
        content = f.read()
        assert "A33X" in content
        # Verify it's marked as in OCL (because A33X is in OCL)
        lines = content.strip().split("\n")
        a33x_line = [l for l in lines if "A33X" in l][0]
        assert ",yes" in a33x_line  # in_opencodelists column should be "yes"
