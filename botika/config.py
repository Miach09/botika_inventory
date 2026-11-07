"""Central settings and shared constants for the Botika Inventory System."""
from pathlib import Path

APP_TITLE = "Botika Inventory Management System"

# --- Paths -------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "botika.db"
LOG_PATH = DATA_DIR / "botika.log"
EXPORT_DIR = BASE_DIR / "exports"

# --- openFDA REST API --------------------------------------------------
OPENFDA_URL = "https://api.fda.gov/drug/label.json"
API_TIMEOUT_SECONDS = 10
API_TEXT_LIMIT = 1800          # max characters kept per label section

# --- Inventory rules ---------------------------------------------------
DEFAULT_REORDER_LEVEL = 10
EXPIRY_WINDOWS = (30, 60, 90)  # days; used for expiry warnings

# Stock movement types and their effect on a batch quantity (+1 add, -1 remove)
MOVEMENT_SIGNS = {
    "RECEIVED": 1,
    "ADJUST_IN": 1,
    "ISSUED": -1,
    "DISPOSED": -1,
    "ADJUST_OUT": -1,
}
MOVEMENT_LABELS = {
    "ISSUED": "Issue / dispense (-)",
    "DISPOSED": "Dispose expired or damaged (-)",
    "ADJUST_IN": "Count adjustment: add (+)",
    "ADJUST_OUT": "Count adjustment: remove (-)",
}
REASON_REQUIRED = {"DISPOSED", "ADJUST_IN", "ADJUST_OUT"}

DOSAGE_FORMS = [
    "Tablet", "Capsule", "Syrup", "Suspension", "Drops",
    "Cream / Ointment", "Injection", "Inhaler", "Sachet", "Other",
]
DEFAULT_CATEGORIES = [
    "Pain & Fever", "Antibiotic", "Allergy", "Cough & Cold",
    "Stomach & Digestive", "Vitamins & Supplements",
    "Maintenance", "First Aid", "Other",
]
