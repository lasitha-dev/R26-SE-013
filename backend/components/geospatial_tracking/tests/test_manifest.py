import csv

from components.geospatial_tracking.data_processing.manifest import build_source_manifest, included_paths

HEADER = [
    "Event ID",
    "Disease",
    "Serotype",
    "latitude",
    "longitude",
    "Locality",
    "Country",
    "Region",
    "observation date",
    "report date",
    "Species",
    "Diagnosis Source",
    "Humans Affected",
    "Human Deaths",
    "Diagnosis Status",
]

ROW = {
    "Event ID": "UNFAO-LEG-1",
    "Disease": "Lumpy skin disease",
    "Serotype": "",
    "latitude": "9.71517",
    "longitude": "80.066849",
    "Locality": "Kopay",
    "Country": "Sri Lanka",
    "Region": "Asia",
    "observation date": "2020-09-07",
    "report date": "2021-01-19",
    "Species": "Domestic - Cattle",
    "Diagnosis Source": "WOAH (former OIE)",
    "Humans Affected": "",
    "Human Deaths": "",
    "Diagnosis Status": "Confirmed",
}


def _write_csv(path, filename):
    p = path / filename
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerow(ROW)
    return p


def test_identical_files_are_deduplicated_by_hash(tmp_path):
    _write_csv(tmp_path, "Latest Reported Events (3).csv")
    _write_csv(tmp_path, "Latest Reported Events (4).csv")

    manifest = build_source_manifest(tmp_path)
    included = [row for row in manifest if row["included_in_canonical"]]
    excluded = [row for row in manifest if not row["included_in_canonical"]]

    assert len(manifest) == 2
    assert len(included) == 1
    assert len(excluded) == 1
    assert included[0]["source_file"] == "Latest Reported Events (3).csv"
    assert excluded[0]["source_file"] == "Latest Reported Events (4).csv"
    assert "byte-identical" in excluded[0]["notes"]


def test_included_paths_excludes_duplicate_hash_file(tmp_path):
    _write_csv(tmp_path, "Latest Reported Events (3).csv")
    _write_csv(tmp_path, "Latest Reported Events (4).csv")

    csv_paths, pdf_paths = included_paths(tmp_path)
    assert len(csv_paths) == 1
    assert csv_paths[0].name == "Latest Reported Events (3).csv"
    assert pdf_paths == []


def test_distinct_content_files_are_both_included(tmp_path):
    _write_csv(tmp_path, "a.csv")
    p2 = tmp_path / "b.csv"
    with p2.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        row2 = dict(ROW, **{"Event ID": "UNFAO-LEG-2", "Locality": "Different Place"})
        writer.writerow(row2)

    csv_paths, _ = included_paths(tmp_path)
    assert len(csv_paths) == 2


def test_manifest_reports_raw_record_count_and_country_coverage(tmp_path):
    _write_csv(tmp_path, "a.csv")
    manifest = build_source_manifest(tmp_path)
    row = manifest[0]
    assert row["raw_record_count"] == 1
    assert row["country_coverage"] == "Sri Lanka"
    assert row["source_system"] == "FAO_EMPRESI_CSV"
