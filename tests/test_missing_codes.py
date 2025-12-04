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
    # Avoid calling the real load_ocl_codes (it asserts large file contents).
    monkeypatch.setattr(mc, "load_ocl_codes", lambda: {"E119", "ZZ99"})

    # Force remote download to fail
    def fake_urlopen(*args, **kwargs):
        raise urllib.error.URLError("no remote")

    monkeypatch.setattr(mc.urllib.request, "urlopen", fake_urlopen)

    # Run main to generate outputs
    mc.main()

    # Check outputs
    out_dir = tmp_path / "reporting_outputs"
    assert (out_dir / "unused_codes.csv").exists()
    assert (out_dir / "missing_codes.csv").exists()
    assert (out_dir / "missing_codes_report.md").exists()

    # Check that warning indicates local fallback
    missing_csv_text = (out_dir / "missing_codes.csv").read_text()
    assert "Remote ZIP unavailable" in missing_csv_text

    # Check that ABC999 appears in missing_codes.csv (missing from OCL)
    txt = (out_dir / "missing_codes.csv").read_text()
    assert "ABC999" in txt


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
    # E119 present with apcs counts
    assert "E119" in reported
    assert "2024-25" in reported["E119"]
    assert reported["E119"]["2024-25"]["apcs_primary_count"] == "30"
    # E120 present with apcs counts
    assert "E120" in reported
    assert "2024-25" in reported["E120"]
    assert reported["E120"]["2024-25"]["apcs_primary_count"] == "30"
    # ABC999 present from ONS
    assert "ABC999" in reported
    assert reported["ABC999"]["2024-25"]["ons_primary_count"] == "1"
    assert reported["ABC999"]["2024-25"]["apcs_primary_count"] == "30"
    assert reported["ABC999"]["2024-25"]["apcs_secondary_count"] == "<15"
    assert reported["ABC999"]["2024-25"]["apcs_all_count"] == "40"
