"""Optional: fill the database with sample data for testing or the demo.

Run once:  python seed_demo.py
Safe to run again; existing records are skipped.
"""
from datetime import date, timedelta

from botika import config
from botika.database import Database, DatabaseError
from botika.services import InventoryService

SUPPLIERS = [("MedSupply Trading", "0917 123 4567", "Quezon City"),
             ("HealthPlus Distributors", "0928 765 4321", "Manila")]

# brand, generic (U.S. name), strength, form, category, reorder, cost
MEDICINES = [
    ("Biogesic", "acetaminophen", "500 mg", "Tablet", "Pain & Fever", 30, 2.50),
    ("Medicol Advance", "ibuprofen", "200 mg", "Capsule", "Pain & Fever", 20, 8.00),
    ("Amoxil", "amoxicillin", "500 mg", "Capsule", "Antibiotic", 20, 12.00),
    ("Virlix", "cetirizine", "10 mg", "Tablet", "Allergy", 15, 7.50),
    ("Claritin", "loratadine", "10 mg", "Tablet", "Allergy", 15, 22.00),
    ("Omepron", "omeprazole", "20 mg", "Capsule", "Stomach & Digestive", 15, 14.00),
    ("Diatabs", "loperamide", "2 mg", "Capsule", "Stomach & Digestive", 10, 9.00),
    ("Ventolin", "albuterol", "100 mcg", "Inhaler", "Cough & Cold", 5, 320.00),
]
# (medicine index, batch no, quantity, days until expiry, supplier index)
BATCHES = [
    (0, "BG-2401", 120, 400, 0), (0, "BG-2307", 15, 20, 0),
    (1, "MA-2402", 40, 250, 1), (2, "AX-2305", 25, 55, 1),
    (3, "VX-2403", 8, 300, 0), (4, "CL-2306", 30, 75, 1),
    (5, "OM-2404", 60, 500, 0), (6, "DT-2301", 12, 12, 1),
    (7, "VT-2402", 4, 180, 0),
]


def main():
    db = Database(config.DB_PATH)
    service = InventoryService(db)
    try:
        today = date.today()
        sup_ids = []
        existing = {s["name"]: s["id"] for s in service.list_suppliers()}
        for name, phone, addr in SUPPLIERS:
            sup_ids.append(existing.get(name) or service.add_supplier(
                {"name": name, "contact_number": phone, "address": addr}))
        cats = {c["name"]: c["id"] for c in service.list_categories()}
        med_ids = []
        existing = {(m["brand_name"], m["strength"]): m["id"] for m in service.list_medicines()}
        for brand, generic, strength, form, cat, reorder, cost in MEDICINES:
            med_ids.append(existing.get((brand, strength)) or service.add_medicine({
                "brand_name": brand, "generic_name": generic, "strength": strength,
                "dosage_form": form, "category_id": cats[cat],
                "reorder_level": reorder, "unit_cost": cost}))
        have = {(b["medicine_id"], b["batch_number"]) for b in service.list_batches()}
        for mi, batch_no, qty, days, si in BATCHES:
            if (med_ids[mi], batch_no) in have:
                continue
            service.receive_batch({
                "medicine_id": med_ids[mi], "supplier_id": sup_ids[si],
                "batch_number": batch_no, "quantity": qty,
                "date_received": (today - timedelta(days=30)).isoformat(),
                "expiry_date": (today + timedelta(days=days)).isoformat()})
        print("Sample data ready.")
    except DatabaseError as exc:
        print("Could not seed data:", exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
