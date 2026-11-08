"""Login, roles (admin deletes, staff does everything else) and 'done by' history."""
import sqlite3

import pytest

from botika import auth
from botika.auth import AuthError
from botika.database import Database
from botika.services import InventoryService
from tests.conftest import in_days


def staff_service(db, service):
    """A second service on the same database, logged in as a staff user."""
    service.add_user("maria", "maria123", auth.ROLE_STAFF)
    other = InventoryService(db)
    other.login("maria", "maria123")
    return other


def test_password_hash_is_salted_and_verifies():
    first, second = auth.hash_password("secret1"), auth.hash_password("secret1")
    assert first != second and "secret1" not in first
    assert auth.verify_password("secret1", first)
    assert not auth.verify_password("secret2", first)
    assert not auth.verify_password("secret1", "not-a-hash")


def test_first_admin_then_login(db):
    svc = InventoryService(db)
    assert not svc.has_users()
    svc.create_first_admin("owner", "secret1")
    with pytest.raises(AuthError):
        svc.create_first_admin("other", "secret1")       # only possible on first run
    assert svc.login("OWNER", "secret1")["role"] == auth.ROLE_ADMIN   # case-insensitive name
    svc.logout()
    assert svc.current_user is None


def test_wrong_password_unknown_user_and_lockout(db):
    svc = InventoryService(db)
    svc.create_first_admin("owner", "secret1")
    for _ in range(auth.MAX_FAILED_LOGINS - 1):
        with pytest.raises(AuthError, match="Wrong username or password"):
            svc.login("owner", "nope")
    with pytest.raises(AuthError, match="Wrong username or password"):
        svc.login("ghost", "secret1")                      # 5th failure starts the lockout
    with pytest.raises(AuthError, match="Too many failed attempts"):
        svc.login("owner", "secret1")                      # even the right password waits


def test_password_and_username_rules(service):
    with pytest.raises(AuthError):
        service.add_user("ab", "secret1", auth.ROLE_STAFF)         # name too short
    with pytest.raises(AuthError):
        service.add_user("juan", "123", auth.ROLE_STAFF)           # password too short
    with pytest.raises(AuthError):
        service.add_user("juan", "secret1", "BOSS")                # unknown role


def test_nobody_can_change_data_before_logging_in(db):
    svc = InventoryService(db)
    with pytest.raises(AuthError, match="log in"):
        svc.add_medicine({"brand_name": "Biogesic", "generic_name": "acetaminophen"})


def test_staff_can_work_but_cannot_delete(db, service, medicine, batch):
    staff = staff_service(db, service)
    staff.add_supplier({"name": "MedSupply"})
    staff.update_medicine(medicine, {"brand_name": "Biogesic", "generic_name": "acetaminophen",
                                     "strength": "500 mg", "dosage_form": "Tablet",
                                     "reorder_level": "15", "unit_cost": "2.50"})
    assert staff.record_movement(batch, {"movement_type": "ISSUED", "quantity": "5"}) == 45
    staff.receive_batch({"medicine_id": medicine, "batch_number": "B-002", "quantity": "10",
                         "expiry_date": in_days(300)})
    for delete, target in ((staff.delete_batch, batch), (staff.delete_medicine, medicine),
                           (staff.delete_supplier, 1)):
        with pytest.raises(AuthError, match="Only an admin can delete"):
            delete(target)
    assert len(staff.list_batches()) == 2                  # nothing was removed


def test_admin_can_delete(service, medicine, batch):
    service.delete_batch(batch)
    service.delete_medicine(medicine)
    assert service.list_medicines() == []


def test_history_records_who_did_it(db, service, medicine):
    batch_id = service.receive_batch({"medicine_id": medicine, "batch_number": "B-9",
                                      "quantity": "20", "expiry_date": in_days(100)})
    staff = staff_service(db, service)
    staff.record_movement(batch_id, {"movement_type": "ISSUED", "quantity": "2"})
    by = [m["performed_by"] for m in service.list_movements(batch_id)]
    assert by == ["maria", "admin"]                        # newest first


def test_movement_export_has_done_by_column(db, service, batch, tmp_path):
    service.record_movement(batch, {"movement_type": "ISSUED", "quantity": "1"})
    path = tmp_path / "movements.csv"
    service.export_movements(path)
    header, *rows = path.read_text(encoding="utf-8-sig").splitlines()
    assert header.endswith("Done By") and rows[0].endswith("admin")


def test_user_management_is_admin_only(db, service):
    staff = staff_service(db, service)
    with pytest.raises(AuthError):
        staff.list_users()
    with pytest.raises(AuthError):
        staff.add_user("juan", "secret1", auth.ROLE_STAFF)
    with pytest.raises(AuthError):
        staff.reset_password(1, "newpass1")


def test_turn_off_reset_and_last_admin_protection(db, service):
    staff = staff_service(db, service)
    maria = next(u for u in service.list_users() if u["username"] == "maria")
    admin = next(u for u in service.list_users() if u["username"] == "admin")
    service.set_user_active(maria["id"], False)
    with pytest.raises(AuthError, match="Wrong username or password"):
        InventoryService(db).login("maria", "maria123")    # turned-off account
    service.set_user_active(maria["id"], True)
    service.reset_password(maria["id"], "brandnew1")
    assert InventoryService(db).login("maria", "brandnew1")
    with pytest.raises(AuthError, match="your own account"):
        service.set_user_active(admin["id"], False)
    assert staff                                            # fixture used above


def test_change_own_password(db, service):
    staff = staff_service(db, service)
    with pytest.raises(AuthError, match="current password"):
        staff.change_own_password("wrong", "another1")
    staff.change_own_password("maria123", "another1")
    assert InventoryService(db).login("maria", "another1")


def test_old_database_is_upgraded(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)                           # a database from before logins
    conn.executescript("""
        CREATE TABLE stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL, quantity INTEGER NOT NULL,
            reason TEXT NOT NULL DEFAULT '', moved_at TEXT NOT NULL);
        INSERT INTO stock_movements(batch_id, movement_type, quantity, moved_at)
            VALUES (1, 'RECEIVED', 5, '2025-01-01 08:00');
    """)
    conn.commit()
    conn.close()
    db = Database(path)
    row = db._conn.execute("SELECT performed_by FROM stock_movements").fetchone()
    assert row["performed_by"] == ""                       # old rows keep working
    assert db.count_users() == 0
    db.close()


def test_admin_can_fix_a_wrong_role(db, service, medicine, batch):
    staff = staff_service(db, service)
    maria = next(u for u in service.list_users() if u["username"] == "maria")
    with pytest.raises(AuthError, match="Only an admin can delete"):
        staff.delete_batch(batch)
    service.set_user_role(maria["id"], auth.ROLE_ADMIN)
    staff.delete_batch(batch)                              # takes effect without re-login
    service.set_user_role(maria["id"], auth.ROLE_STAFF)
    with pytest.raises(AuthError, match="Only an admin can delete"):
        staff.delete_medicine(medicine)                    # demotion is immediate too


def test_role_change_rules(db, service):
    staff = staff_service(db, service)
    admin = next(u for u in service.list_users() if u["username"] == "admin")
    maria = next(u for u in service.list_users() if u["username"] == "maria")
    with pytest.raises(AuthError, match="Only an admin can change roles"):
        staff.set_user_role(maria["id"], auth.ROLE_ADMIN)
    with pytest.raises(AuthError, match="your own role"):
        service.set_user_role(admin["id"], auth.ROLE_STAFF)
    with pytest.raises(AuthError):
        service.set_user_role(maria["id"], "BOSS")
    service.set_user_role(maria["id"], auth.ROLE_ADMIN)
    # with two admins, either can demote the other
    maria_admin = InventoryService(db)
    maria_admin.login("maria", "maria123")
    maria_admin.set_user_role(admin["id"], auth.ROLE_STAFF)
    assert staff                                            # fixture used above


def test_turned_off_user_is_blocked_while_logged_in(db, service, medicine):
    staff = staff_service(db, service)
    maria = next(u for u in service.list_users() if u["username"] == "maria")
    service.set_user_active(maria["id"], False)
    with pytest.raises(AuthError, match="turned off"):
        staff.add_supplier({"name": "MedSupply"})
