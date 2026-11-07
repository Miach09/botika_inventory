"""Input validation and expiry/stock business rules."""
from datetime import date

import pytest

from botika import rules
from botika.validators import (ValidationError, validate_batch, validate_medicine,
                               validate_movement, validate_supplier)
from tests.conftest import in_days


def test_medicine_requires_names():
    with pytest.raises(ValidationError) as err:
        validate_medicine({"brand_name": " ", "generic_name": ""})
    assert len(err.value.errors) == 2


@pytest.mark.parametrize("field,value", [("reorder_level", "abc"), ("reorder_level", "-1"),
                                         ("unit_cost", "free"), ("unit_cost", "-5")])
def test_medicine_rejects_bad_numbers(field, value):
    with pytest.raises(ValidationError):
        validate_medicine({"brand_name": "A", "generic_name": "b", field: value})


def test_medicine_defaults_and_trimming():
    data = validate_medicine({"brand_name": "  Biogesic ", "generic_name": "acetaminophen"})
    assert data["brand_name"] == "Biogesic" and data["reorder_level"] == 10
    assert data["unit_cost"] == 0.0


def test_generic_name_cannot_contain_quotes():
    with pytest.raises(ValidationError):
        validate_medicine({"brand_name": "A", "generic_name": 'bad"name'})


def test_supplier_phone_validation():
    assert validate_supplier({"name": "X", "contact_number": "0917 123 4567"})
    with pytest.raises(ValidationError):
        validate_supplier({"name": "X", "contact_number": "call me"})
    with pytest.raises(ValidationError):
        validate_supplier({"name": ""})


def test_batch_rejects_missing_and_bad_input():
    with pytest.raises(ValidationError) as err:
        validate_batch({"medicine_id": None, "batch_number": "", "quantity": "0",
                        "expiry_date": "2025-13-45"})
    assert len(err.value.errors) >= 4


def test_batch_rejects_expired_stock_and_bad_order():
    base = {"medicine_id": 1, "batch_number": "B1", "quantity": "5"}
    with pytest.raises(ValidationError):
        validate_batch({**base, "expiry_date": in_days(-5), "date_received": in_days(-30)})
    with pytest.raises(ValidationError):
        validate_batch({**base, "expiry_date": in_days(10), "date_received": in_days(20)})


def test_valid_batch_passes():
    data = validate_batch({"medicine_id": "1", "batch_number": "B-1", "quantity": "5",
                           "expiry_date": in_days(100)})
    assert data["quantity"] == 5 and data["supplier_id"] is None


def test_movement_validation():
    with pytest.raises(ValidationError):
        validate_movement({"movement_type": "RECEIVED", "quantity": "1"})
    with pytest.raises(ValidationError):
        validate_movement({"movement_type": "ISSUED", "quantity": "0"})
    assert validate_movement({"movement_type": "ISSUED", "quantity": "2"})["quantity"] == 2


def test_expiry_status_boundaries():
    today = date(2026, 1, 1)
    assert rules.expiry_status("2025-12-31", today) == rules.EXPIRED
    assert rules.expiry_status("2026-01-01", today) == rules.EXPIRING_30    # expires today
    assert rules.expiry_status("2026-01-31", today) == rules.EXPIRING_30
    assert rules.expiry_status("2026-02-01", today) == rules.EXPIRING_60
    assert rules.expiry_status("2026-03-02", today) == rules.EXPIRING_60
    assert rules.expiry_status("2026-04-01", today) == rules.EXPIRING_90
    assert rules.expiry_status("2026-04-02", today) == rules.OK


def test_stock_status():
    assert rules.stock_status(0, 10) == "OUT"
    assert rules.stock_status(10, 10) == "LOW"
    assert rules.stock_status(11, 10) == "OK"


def test_batch_filters_and_dashboard(service, medicine, db):
    for no, qty, days in (("A", 10, -2), ("B", 10, 10), ("C", 10, 50), ("D", 10, 300)):
        db.receive_batch({"medicine_id": medicine, "supplier_id": None, "batch_number": no,
                          "quantity": qty, "date_received": in_days(-400),
                          "expiry_date": in_days(days)})
    names = lambda f: sorted(b["batch_number"] for b in service.list_batches(status_filter=f))
    assert names("EXPIRED") == ["A"]
    assert names("WITHIN_30") == ["B"]
    assert names("WITHIN_60") == ["B", "C"]
    assert names("OK") == ["D"]
    summary = service.dashboard_summary()
    assert summary["expired"] == 1 and summary["expiring_30"] == 1 and summary["units"] == 30
    kinds = [a[0] for a in service.alerts()]
    assert kinds[:2] == ["Expired", "Expiring soon"]
