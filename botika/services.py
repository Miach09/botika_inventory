"""Application logic: validates input, applies rules, coordinates the layers.

The GUI only ever talks to InventoryService. The service in turn uses the
database layer, the API client and the file/report layer, so each of those can
change without touching the interface.
"""
from datetime import date

from botika import config, rules, validators
from botika.api_client import DrugInfo, DrugInfoClient
from botika.database import Database
from botika.reports import ReportError, read_csv, write_csv
from botika.validators import ValidationError

IMPORT_HEADERS = ["brand_name", "generic_name", "strength", "dosage_form",
                  "category", "reorder_level", "unit_cost"]

BATCH_FILTERS = {
    "ALL": "All batches",
    "IN_STOCK": "In stock only (hide empty)",
    "EXPIRED": "Expired",
    "WITHIN_30": "Expiring within 30 days",
    "WITHIN_60": "Expiring within 60 days",
    "WITHIN_90": "Expiring within 90 days",
    "OK": "Good (not expiring soon)",
}


class InventoryService:
    def __init__(self, db: Database, drug_client: DrugInfoClient | None = None):
        self.db = db
        self.drug_client = drug_client or DrugInfoClient()

    # ---- categories & suppliers --------------------------------------
    def list_categories(self):
        return self.db.list_categories()

    def list_suppliers(self, search=""):
        return self.db.list_suppliers(search)

    def add_supplier(self, raw):
        data = validators.validate_supplier(raw)
        return self.db.add_supplier(**data)

    def update_supplier(self, supplier_id, raw):
        data = validators.validate_supplier(raw)
        self.db.update_supplier(supplier_id, **data)

    def delete_supplier(self, supplier_id):
        self.db.delete_supplier(supplier_id)

    # ---- medicines ---------------------------------------------------
    def list_medicines(self, search="", category_id=None, today: date | None = None):
        rows = self.db.list_medicines(search, category_id, today)
        for row in rows:
            row["stock_status"] = rules.stock_status(row["usable_stock"],
                                                     row["reorder_level"])
        return rows

    def add_medicine(self, raw):
        return self.db.add_medicine(validators.validate_medicine(raw))

    def update_medicine(self, medicine_id, raw):
        self.db.update_medicine(medicine_id, validators.validate_medicine(raw))

    def delete_medicine(self, medicine_id):
        self.db.delete_medicine(medicine_id)

    # ---- drug information (REST API) ---------------------------------
    def lookup_drug_info(self, generic_name: str) -> DrugInfo:
        """Calls the API only (no database access), so it is safe in a thread."""
        return self.drug_client.fetch(generic_name)

    def save_drug_info(self, medicine_id, info: DrugInfo):
        self.db.save_drug_info(medicine_id, info.to_text())

    # ---- stock batches -----------------------------------------------
    def list_batches(self, search="", status_filter="ALL", medicine_id=None,
                     today: date | None = None):
        today = today or date.today()
        out = []
        for row in self.db.list_batches(search, medicine_id):
            days = rules.days_until(row["expiry_date"], today)
            if row["quantity"] == 0:
                status = rules.DEPLETED
            else:
                status = rules.expiry_status(row["expiry_date"], today)
            row["days_left"] = days
            row["status"] = status
            row["status_label"] = rules.STATUS_LABELS[status]
            if self._matches_filter(row, status_filter, days):
                out.append(row)
        return out

    @staticmethod
    def _matches_filter(row, status_filter, days) -> bool:
        if status_filter in (None, "ALL"):
            return True
        if status_filter == "IN_STOCK":
            return row["quantity"] > 0
        if row["quantity"] == 0:
            return False
        if status_filter == "EXPIRED":
            return days < 0
        if status_filter == "OK":
            return days > config.EXPIRY_WINDOWS[-1]
        if status_filter.startswith("WITHIN_"):
            return 0 <= days <= int(status_filter.split("_")[1])
        return True

    def receive_batch(self, raw, today: date | None = None):
        data = validators.validate_batch(raw, creating=True, today=today)
        return self.db.receive_batch(data)

    def update_batch(self, batch_id, raw, today: date | None = None):
        data = validators.validate_batch(raw, creating=False, today=today)
        self.db.update_batch(batch_id, data)

    def delete_batch(self, batch_id):
        self.db.delete_batch(batch_id)

    def record_movement(self, batch_id, raw):
        data = validators.validate_movement(raw)
        return self.db.record_movement(batch_id, data["movement_type"],
                                       data["quantity"], data["reason"])

    def list_movements(self, batch_id=None):
        return self.db.list_movements(batch_id)

    # ---- stock alerts ------------------------------------------------
    def stock_alerts(self, today: date | None = None) -> list:
        """Medicines that are OUT or LOW, with the supplier of their latest batch."""
        meds = [m for m in self.list_medicines(today=today)
                if m["stock_status"] in ("OUT", "LOW")]
        latest = {}
        for b in self.db.list_batches():
            current = latest.get(b["medicine_id"])
            if current is None or b["date_received"] >= current[0]:
                latest[b["medicine_id"]] = (b["date_received"], b["supplier"] or "")
        for m in meds:
            m["last_supplier"] = latest.get(m["id"], ("", ""))[1]
        meds.sort(key=lambda m: (m["stock_status"] != "OUT", m["usable_stock"],
                                 m["brand_name"].lower()))
        return meds

    # ---- dashboard ---------------------------------------------------
    def dashboard_summary(self, today: date | None = None) -> dict:
        today = today or date.today()
        medicines = self.list_medicines(today=today)
        batches = self.list_batches(today=today)
        live = [b for b in batches if b["quantity"] > 0]
        return {
            "medicines": len(medicines),
            "units": sum(m["usable_stock"] for m in medicines),
            "low_stock": sum(1 for m in medicines if m["stock_status"] in ("LOW", "OUT")),
            "expiring_30": sum(1 for b in live if b["status"] == rules.EXPIRING_30),
            "expired": sum(1 for b in live if b["status"] == rules.EXPIRED),
            "value": round(sum(b["quantity"] * b["unit_cost"] for b in live
                               if b["status"] != rules.EXPIRED), 2),
        }

    def alerts(self, today: date | None = None) -> list:
        """Rows for the dashboard: expired, expiring soon, and low-stock items."""
        today = today or date.today()
        alerts = []
        for b in self.list_batches(today=today):
            if b["quantity"] == 0:
                continue
            label = f"{b['brand_name']} {b['strength']}".strip()
            if b["status"] == rules.EXPIRED:
                alerts.append(("Expired", label,
                               f"Batch {b['batch_number']}: {b['quantity']} unit(s) "
                               f"expired on {b['expiry_date']}", 0))
            elif b["status"] == rules.EXPIRING_30:
                alerts.append(("Expiring soon", label,
                               f"Batch {b['batch_number']}: {b['quantity']} unit(s) "
                               f"expire in {b['days_left']} day(s)", 1))
        for m in self.list_medicines(today=today):
            label = f"{m['brand_name']} {m['strength']}".strip()
            if m["stock_status"] == "OUT":
                alerts.append(("Out of stock", label, "No usable stock left", 2))
            elif m["stock_status"] == "LOW":
                alerts.append(("Low stock", label,
                               f"{m['usable_stock']} left (reorder level "
                               f"{m['reorder_level']})", 3))
        alerts.sort(key=lambda a: a[3])
        return [a[:3] for a in alerts]

    # ---- reports / files ---------------------------------------------
    def export_medicines(self, path) -> int:
        rows = [[m["brand_name"], m["generic_name"], m["strength"], m["dosage_form"],
                 m["category"] or "", m["usable_stock"], m["expired_stock"],
                 m["reorder_level"], m["stock_status"], f"{m['unit_cost']:.2f}"]
                for m in self.list_medicines()]
        return write_csv(path, ["Brand", "Generic", "Strength", "Form", "Category",
                                "Usable Stock", "Expired Stock", "Reorder Level",
                                "Stock Status", "Unit Cost"], rows)

    def export_batches(self, path) -> int:
        return write_csv(path, *self._batch_table(self.list_batches()))

    def export_expiry_report(self, path, days: int) -> int:
        """Batches already expired or expiring within `days` days (with stock left)."""
        selected = [b for b in self.list_batches()
                    if b["quantity"] > 0 and b["days_left"] <= days]
        selected.sort(key=lambda b: b["days_left"])
        return write_csv(path, *self._batch_table(selected))

    @staticmethod
    def _batch_table(batches):
        headers = ["Brand", "Generic", "Strength", "Batch No.", "Quantity",
                   "Received", "Expiry", "Days Left", "Status", "Supplier"]
        rows = [[b["brand_name"], b["generic_name"], b["strength"], b["batch_number"],
                 b["quantity"], b["date_received"], b["expiry_date"], b["days_left"],
                 b["status_label"], b["supplier"] or ""] for b in batches]
        return headers, rows

    def export_movements(self, path) -> int:
        rows = [[m["moved_at"], m["brand_name"], m["strength"], m["batch_number"],
                 m["movement_type"], m["quantity"], m["reason"]]
                for m in self.list_movements()]
        return write_csv(path, ["Date/Time", "Brand", "Strength", "Batch No.",
                                "Movement", "Quantity", "Reason"], rows)

    def write_import_template(self, path) -> int:
        sample = [["Biogesic", "acetaminophen", "500 mg", "Tablet",
                   "Pain & Fever", "20", "2.50"]]
        return write_csv(path, IMPORT_HEADERS, sample)

    def import_medicines(self, path):
        """Import medicines from CSV. Returns (added, skipped, error_messages)."""
        rows = read_csv(path, ["brand_name", "generic_name"])
        categories = {c["name"].lower(): c["id"] for c in self.list_categories()}
        added, skipped, errors = 0, 0, []
        for line_no, row in rows:
            raw = dict(row)
            raw["category_id"] = categories.get(row.get("category", "").lower())
            try:
                self.add_medicine(raw)
                added += 1
            except ValidationError as exc:
                skipped += 1
                errors.append(f"Line {line_no}: " + " ".join(exc.errors))
            except Exception as exc:  # duplicates and other database conflicts
                skipped += 1
                errors.append(f"Line {line_no}: {exc}")
        return added, skipped, errors
