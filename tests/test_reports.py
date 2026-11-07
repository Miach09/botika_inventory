"""CSV export/import and file error handling."""
import csv
import os

import pytest

from botika.reports import ReportError, read_csv, write_csv
from tests.conftest import in_days


def test_export_medicines_and_batches(service, medicine, batch, tmp_path):
    out = tmp_path / "meds.csv"
    assert service.export_medicines(out) == 1
    rows = list(csv.reader(open(out, encoding="utf-8-sig")))
    assert rows[0][0] == "Brand" and rows[1][0] == "Biogesic" and rows[1][5] == "50"
    assert service.export_batches(tmp_path / "b.csv") == 1
    assert service.export_movements(tmp_path / "m.csv") == 1


def test_expiry_report_only_includes_items_in_window(service, medicine, db, tmp_path):
    for no, days in (("A", -1), ("B", 20), ("C", 200)):
        db.receive_batch({"medicine_id": medicine, "supplier_id": None, "batch_number": no,
                          "quantity": 5, "date_received": in_days(-300),
                          "expiry_date": in_days(days)})
    assert service.export_expiry_report(tmp_path / "e.csv", 30) == 2


def test_export_to_missing_folder(service):
    with pytest.raises(ReportError) as err:
        service.export_medicines("/no/such/folder/out.csv")
    assert "does not exist" in str(err.value)


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0,
                    reason="file permission test only works on Linux/Mac as a normal user")
def test_export_permission_denied(service, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    with pytest.raises(ReportError):
        service.export_medicines(locked / "out.csv")


def test_import_valid_invalid_and_duplicate_rows(service, tmp_path):
    path = tmp_path / "in.csv"
    path.write_text(
        "brand_name,generic_name,strength,dosage_form,category,reorder_level,unit_cost\n"
        "Biogesic,acetaminophen,500 mg,Tablet,Pain & Fever,20,2.5\n"
        "Biogesic,acetaminophen,500 mg,Tablet,Pain & Fever,20,2.5\n"   # duplicate
        ",ibuprofen,200 mg,Capsule,,10,1\n"                            # missing brand
        "Virlix,cetirizine,10 mg,Tablet,Allergy,abc,7\n",              # bad number
        encoding="utf-8")
    added, skipped, errors = service.import_medicines(path)
    assert (added, skipped) == (1, 3) and len(errors) == 3
    assert service.list_medicines()[0]["category"] == "Pain & Fever"


def test_import_missing_columns_and_file(service, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,price\nx,1\n", encoding="utf-8")
    with pytest.raises(ReportError) as err:
        service.import_medicines(bad)
    assert "missing" in str(err.value)
    with pytest.raises(ReportError):
        service.import_medicines(tmp_path / "nope.csv")


def test_import_empty_and_binary_files(service, tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(ReportError):
        read_csv(empty, ["brand_name"])
    binary = tmp_path / "bin.csv"
    binary.write_bytes(b"\xff\xfe\x00\x81\x82")
    with pytest.raises(ReportError):
        read_csv(binary, ["brand_name"])


def test_template_roundtrip(service, tmp_path):
    path = tmp_path / "t.csv"
    service.write_import_template(path)
    assert service.import_medicines(path)[0] == 1
    assert write_csv(tmp_path / "x.csv", ["a"], [[1], [2]]) == 2
