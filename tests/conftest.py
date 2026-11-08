import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from botika.database import Database  # noqa: E402
from botika.services import InventoryService  # noqa: E402


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def service(db):
    """A service with an admin logged in (the app always requires a login)."""
    svc = InventoryService(db)
    svc.create_first_admin("admin", "secret1")
    svc.login("admin", "secret1")
    return svc


@pytest.fixture
def medicine(service):
    return service.add_medicine({
        "brand_name": "Biogesic", "generic_name": "acetaminophen",
        "strength": "500 mg", "dosage_form": "Tablet",
        "reorder_level": "10", "unit_cost": "2.50"})


def in_days(n):
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.fixture
def batch(service, medicine):
    return service.receive_batch({
        "medicine_id": medicine, "batch_number": "B-001",
        "quantity": "50", "expiry_date": in_days(200)})
