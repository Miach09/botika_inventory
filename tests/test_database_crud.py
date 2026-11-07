"""CRUD, search, constraints and stock movements (database + service layers)."""
import pytest

from botika.database import ConflictError, InsufficientStockError, NotFoundError
from botika.validators import ValidationError
from tests.conftest import in_days

MED = {"brand_name": "Medicol", "generic_name": "ibuprofen", "strength": "200 mg",
       "dosage_form": "Capsule", "reorder_level": "20", "unit_cost": "8"}


def test_create_and_read_medicine(service):
    mid = service.add_medicine(MED)
    rows = service.list_medicines()
    assert len(rows) == 1 and rows[0]["id"] == mid
    assert rows[0]["generic_name"] == "ibuprofen" and rows[0]["usable_stock"] == 0


def test_update_medicine(service, medicine):
    service.update_medicine(medicine, {**MED, "brand_name": "Biogesic Plus"})
    assert service.list_medicines()[0]["brand_name"] == "Biogesic Plus"


def test_delete_medicine(service, medicine):
    service.delete_medicine(medicine)
    assert service.list_medicines() == []


def test_delete_missing_medicine_raises(service):
    with pytest.raises(NotFoundError):
        service.delete_medicine(999)


def test_duplicate_medicine_is_rejected(service, medicine):
    with pytest.raises(ConflictError):
        service.add_medicine({"brand_name": "Biogesic", "generic_name": "acetaminophen",
                              "strength": "500 mg", "dosage_form": "Tablet"})


def test_search_by_brand_and_generic(service, medicine):
    service.add_medicine(MED)
    assert [m["brand_name"] for m in service.list_medicines("bio")] == ["Biogesic"]
    assert [m["brand_name"] for m in service.list_medicines("IBUPRO")] == ["Medicol"]
    assert service.list_medicines("zzz") == []


def test_filter_by_category(service):
    cats = {c["name"]: c["id"] for c in service.list_categories()}
    service.add_medicine({**MED, "category_id": cats["Allergy"]})
    assert len(service.list_medicines(category_id=cats["Allergy"])) == 1
    assert service.list_medicines(category_id=cats["Antibiotic"]) == []


def test_sql_injection_text_is_treated_as_data(service, medicine):
    assert service.list_medicines("'; DROP TABLE medicines; --") == []
    assert len(service.list_medicines()) == 1     # table still exists


def test_supplier_crud(service):
    sid = service.add_supplier({"name": "MedSupply", "contact_number": "0917 123 4567"})
    service.update_supplier(sid, {"name": "MedSupply Inc", "contact_number": "0917 123 4567"})
    assert service.list_suppliers("inc")[0]["name"] == "MedSupply Inc"
    service.delete_supplier(sid)
    assert service.list_suppliers() == []


def test_receive_batch_creates_stock_and_movement(service, medicine, batch):
    assert service.list_medicines()[0]["usable_stock"] == 50
    moves = service.list_movements(batch)
    assert len(moves) == 1 and moves[0]["movement_type"] == "RECEIVED"


def test_medicine_with_batches_cannot_be_deleted(service, medicine, batch):
    with pytest.raises(ConflictError):
        service.delete_medicine(medicine)
    assert len(service.list_medicines()) == 1


def test_issue_stock_reduces_quantity(service, batch):
    assert service.record_movement(batch, {"movement_type": "ISSUED", "quantity": "5"}) == 45


def test_cannot_issue_more_than_available(service, batch):
    with pytest.raises(InsufficientStockError):
        service.record_movement(batch, {"movement_type": "ISSUED", "quantity": "51"})
    assert service.list_batches()[0]["quantity"] == 50     # unchanged


def test_adjustment_requires_reason(service, batch):
    with pytest.raises(ValidationError):
        service.record_movement(batch, {"movement_type": "ADJUST_OUT", "quantity": "2"})
    service.record_movement(batch, {"movement_type": "ADJUST_OUT", "quantity": "2",
                                    "reason": "Count correction"})
    assert service.list_batches()[0]["quantity"] == 48


def test_delete_batch_removes_its_history(service, batch):
    service.delete_batch(batch)
    assert service.list_batches() == [] and service.list_movements() == []


def test_expired_stock_is_not_usable(service, medicine, db):
    db.receive_batch({"medicine_id": medicine, "supplier_id": None, "batch_number": "OLD",
                      "quantity": 30, "date_received": in_days(-100),
                      "expiry_date": in_days(-1)})
    row = service.list_medicines()[0]
    assert row["usable_stock"] == 0 and row["expired_stock"] == 30
    assert row["stock_status"] == "OUT"


def test_data_persists_after_reopening(tmp_path):
    from botika.database import Database
    from botika.services import InventoryService
    path = tmp_path / "persist.db"
    first = Database(path)
    InventoryService(first).add_medicine(MED)
    first.close()
    second = InventoryService(Database(path))
    assert second.list_medicines()[0]["brand_name"] == "Medicol"
