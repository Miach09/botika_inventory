"""Database layer: the only module that talks to SQLite.

All queries are parameterized (?) so user input can never change the SQL.
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from botika import config


class DatabaseError(Exception):
    """Base class for database problems shown to the user."""


class NotFoundError(DatabaseError):
    """The requested record does not exist."""


class ConflictError(DatabaseError):
    """A duplicate or a still-referenced record blocked the operation."""


class InsufficientStockError(DatabaseError):
    """A stock movement would make a batch quantity negative."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS suppliers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    contact_number TEXT NOT NULL DEFAULT '',
    address        TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS medicines (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name        TEXT NOT NULL,
    generic_name      TEXT NOT NULL,
    strength          TEXT NOT NULL DEFAULT '',
    dosage_form       TEXT NOT NULL DEFAULT '',
    category_id       INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    reorder_level     INTEGER NOT NULL DEFAULT 10 CHECK (reorder_level >= 0),
    unit_cost         REAL    NOT NULL DEFAULT 0  CHECK (unit_cost >= 0),
    drug_info         TEXT,
    drug_info_fetched TEXT,
    UNIQUE (brand_name, strength, dosage_form)
);
CREATE TABLE IF NOT EXISTS stock_batches (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id      INTEGER NOT NULL REFERENCES medicines(id) ON DELETE RESTRICT,
    supplier_id      INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    batch_number     TEXT NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity >= 0),
    initial_quantity INTEGER NOT NULL CHECK (initial_quantity > 0),
    date_received    TEXT NOT NULL,
    expiry_date      TEXT NOT NULL,
    UNIQUE (medicine_id, batch_number)
);
CREATE TABLE IF NOT EXISTS stock_movements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id      INTEGER NOT NULL REFERENCES stock_batches(id) ON DELETE CASCADE,
    movement_type TEXT NOT NULL
        CHECK (movement_type IN ('RECEIVED','ISSUED','DISPOSED','ADJUST_IN','ADJUST_OUT')),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    reason        TEXT NOT NULL DEFAULT '',
    moved_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_batches_medicine ON stock_batches(medicine_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiry   ON stock_batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_movements_batch  ON stock_movements(batch_id);
"""

MEDICINE_FIELDS = ("brand_name", "generic_name", "strength", "dosage_form",
                   "category_id", "reorder_level", "unit_cost")


def _friendly(exc: sqlite3.IntegrityError) -> str:
    text = str(exc)
    if "UNIQUE" in text:
        return "A record with the same details already exists."
    if "FOREIGN KEY" in text:
        return ("This record is linked to other records (for example, a medicine "
                "that still has stock batches) and cannot be changed or deleted.")
    return "The data breaks a database rule and could not be saved."


class Database:
    def __init__(self, path=config.DB_PATH):
        self.path = str(path)
        try:
            if self.path != ":memory:":
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self.create_tables()
        except (sqlite3.Error, OSError) as exc:
            raise DatabaseError(f"Could not open the database file: {exc}") from exc

    # ---- plumbing ----------------------------------------------------
    @contextmanager
    def _transaction(self):
        try:
            yield self._conn
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ConflictError(_friendly(exc)) from exc
        except sqlite3.Error as exc:
            self._conn.rollback()
            raise DatabaseError(f"Database error: {exc}") from exc
        except Exception:
            self._conn.rollback()
            raise

    def _fetch(self, sql, params=()):
        try:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]
        except sqlite3.Error as exc:
            raise DatabaseError(f"Database error: {exc}") from exc

    def create_tables(self):
        with self._transaction() as conn:
            conn.executescript(SCHEMA)
            conn.executemany("INSERT OR IGNORE INTO categories(name) VALUES (?)",
                             [(c,) for c in config.DEFAULT_CATEGORIES])

    def close(self):
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    # ---- categories --------------------------------------------------
    def list_categories(self):
        return self._fetch("SELECT id, name FROM categories ORDER BY name")

    # ---- suppliers ---------------------------------------------------
    def add_supplier(self, name, contact_number="", address=""):
        with self._transaction() as conn:
            cur = conn.execute(
                "INSERT INTO suppliers(name, contact_number, address) VALUES (?,?,?)",
                (name, contact_number, address))
            return cur.lastrowid

    def update_supplier(self, supplier_id, name, contact_number="", address=""):
        with self._transaction() as conn:
            cur = conn.execute(
                "UPDATE suppliers SET name=?, contact_number=?, address=? WHERE id=?",
                (name, contact_number, address, supplier_id))
            if cur.rowcount == 0:
                raise NotFoundError("That supplier no longer exists.")

    def delete_supplier(self, supplier_id):
        with self._transaction() as conn:
            cur = conn.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))
            if cur.rowcount == 0:
                raise NotFoundError("That supplier no longer exists.")

    def list_suppliers(self, search=""):
        like = f"%{search.strip()}%"
        return self._fetch(
            "SELECT * FROM suppliers WHERE name LIKE ? OR contact_number LIKE ? "
            "OR address LIKE ? ORDER BY name", (like, like, like))

    # ---- medicines ---------------------------------------------------
    def add_medicine(self, data: dict):
        with self._transaction() as conn:
            cur = conn.execute(
                "INSERT INTO medicines(brand_name, generic_name, strength, dosage_form,"
                " category_id, reorder_level, unit_cost) VALUES (?,?,?,?,?,?,?)",
                tuple(data[f] for f in MEDICINE_FIELDS))
            return cur.lastrowid

    def update_medicine(self, medicine_id, data: dict):
        with self._transaction() as conn:
            cur = conn.execute(
                "UPDATE medicines SET brand_name=?, generic_name=?, strength=?,"
                " dosage_form=?, category_id=?, reorder_level=?, unit_cost=? WHERE id=?",
                tuple(data[f] for f in MEDICINE_FIELDS) + (medicine_id,))
            if cur.rowcount == 0:
                raise NotFoundError("That medicine no longer exists.")

    def delete_medicine(self, medicine_id):
        with self._transaction() as conn:
            cur = conn.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))
            if cur.rowcount == 0:
                raise NotFoundError("That medicine no longer exists.")

    def save_drug_info(self, medicine_id, text):
        with self._transaction() as conn:
            cur = conn.execute(
                "UPDATE medicines SET drug_info=?, drug_info_fetched=? WHERE id=?",
                (text, datetime.now().strftime("%Y-%m-%d %H:%M"), medicine_id))
            if cur.rowcount == 0:
                raise NotFoundError("That medicine no longer exists.")

    def list_medicines(self, search="", category_id=None, today: date | None = None):
        """Medicines with usable (non-expired) and expired stock totals."""
        today_s = (today or date.today()).isoformat()
        like = f"%{search.strip()}%"
        sql = """
            SELECT m.*, c.name AS category,
                   COALESCE(SUM(CASE WHEN b.expiry_date >= ? THEN b.quantity END), 0)
                       AS usable_stock,
                   COALESCE(SUM(CASE WHEN b.expiry_date <  ? THEN b.quantity END), 0)
                       AS expired_stock
            FROM medicines m
            LEFT JOIN categories c    ON c.id = m.category_id
            LEFT JOIN stock_batches b ON b.medicine_id = m.id
            WHERE (m.brand_name LIKE ? OR m.generic_name LIKE ?)
        """
        params = [today_s, today_s, like, like]
        if category_id is not None:
            sql += " AND m.category_id = ?"
            params.append(category_id)
        sql += " GROUP BY m.id ORDER BY m.brand_name COLLATE NOCASE"
        return self._fetch(sql, params)

    # ---- stock batches -----------------------------------------------
    def receive_batch(self, data: dict):
        """Create a batch and log the RECEIVED movement in one transaction."""
        with self._transaction() as conn:
            cur = conn.execute(
                "INSERT INTO stock_batches(medicine_id, supplier_id, batch_number,"
                " quantity, initial_quantity, date_received, expiry_date)"
                " VALUES (?,?,?,?,?,?,?)",
                (data["medicine_id"], data["supplier_id"], data["batch_number"],
                 data["quantity"], data["quantity"], data["date_received"],
                 data["expiry_date"]))
            batch_id = cur.lastrowid
            conn.execute(
                "INSERT INTO stock_movements(batch_id, movement_type, quantity,"
                " reason, moved_at) VALUES (?, 'RECEIVED', ?, ?, ?)",
                (batch_id, data["quantity"], "Initial stock received",
                 datetime.now().strftime("%Y-%m-%d %H:%M")))
            return batch_id

    def update_batch(self, batch_id, data: dict):
        with self._transaction() as conn:
            cur = conn.execute(
                "UPDATE stock_batches SET medicine_id=?, supplier_id=?, batch_number=?,"
                " date_received=?, expiry_date=? WHERE id=?",
                (data["medicine_id"], data["supplier_id"], data["batch_number"],
                 data["date_received"], data["expiry_date"], batch_id))
            if cur.rowcount == 0:
                raise NotFoundError("That batch no longer exists.")

    def delete_batch(self, batch_id):
        with self._transaction() as conn:
            cur = conn.execute("DELETE FROM stock_batches WHERE id=?", (batch_id,))
            if cur.rowcount == 0:
                raise NotFoundError("That batch no longer exists.")

    def get_batch(self, batch_id):
        rows = self._fetch("SELECT * FROM stock_batches WHERE id=?", (batch_id,))
        if not rows:
            raise NotFoundError("That batch no longer exists.")
        return rows[0]

    def list_batches(self, search="", medicine_id=None):
        like = f"%{search.strip()}%"
        sql = """
            SELECT b.*, m.brand_name, m.generic_name, m.strength, m.dosage_form,
                   m.unit_cost, s.name AS supplier
            FROM stock_batches b
            JOIN medicines m      ON m.id = b.medicine_id
            LEFT JOIN suppliers s ON s.id = b.supplier_id
            WHERE (m.brand_name LIKE ? OR m.generic_name LIKE ?
                   OR b.batch_number LIKE ?)
        """
        params = [like, like, like]
        if medicine_id is not None:
            sql += " AND b.medicine_id = ?"
            params.append(medicine_id)
        sql += " ORDER BY b.expiry_date ASC, m.brand_name COLLATE NOCASE"
        return self._fetch(sql, params)

    # ---- stock movements ---------------------------------------------
    def record_movement(self, batch_id, movement_type, quantity, reason=""):
        """Change a batch quantity and log it atomically (never below zero)."""
        sign = config.MOVEMENT_SIGNS[movement_type]
        with self._transaction() as conn:
            row = conn.execute("SELECT quantity FROM stock_batches WHERE id=?",
                               (batch_id,)).fetchone()
            if row is None:
                raise NotFoundError("That batch no longer exists.")
            new_qty = row["quantity"] + sign * quantity
            if new_qty < 0:
                raise InsufficientStockError(
                    f"Only {row['quantity']} unit(s) are left in this batch.")
            conn.execute("UPDATE stock_batches SET quantity=? WHERE id=?",
                         (new_qty, batch_id))
            conn.execute(
                "INSERT INTO stock_movements(batch_id, movement_type, quantity,"
                " reason, moved_at) VALUES (?,?,?,?,?)",
                (batch_id, movement_type, quantity, reason,
                 datetime.now().strftime("%Y-%m-%d %H:%M")))
            return new_qty

    def list_movements(self, batch_id=None):
        sql = """
            SELECT mv.*, b.batch_number, m.brand_name, m.strength
            FROM stock_movements mv
            JOIN stock_batches b ON b.id = mv.batch_id
            JOIN medicines m     ON m.id = b.medicine_id
        """
        params = []
        if batch_id is not None:
            sql += " WHERE mv.batch_id = ?"
            params.append(batch_id)
        sql += " ORDER BY mv.id DESC"
        return self._fetch(sql, params)
