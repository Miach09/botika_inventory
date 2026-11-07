"""Business rules that do not need a database or a GUI.

Keeping them here (pure functions) makes them easy to reuse and to test.
"""
from datetime import date, datetime

from botika import config

# Expiry statuses
EXPIRED = "EXPIRED"
EXPIRING_30 = "EXPIRING_30"
EXPIRING_60 = "EXPIRING_60"
EXPIRING_90 = "EXPIRING_90"
OK = "OK"
DEPLETED = "DEPLETED"

STATUS_LABELS = {
    EXPIRED: "Expired",
    EXPIRING_30: "Expiring (30d)",
    EXPIRING_60: "Expiring (60d)",
    EXPIRING_90: "Expiring (90d)",
    OK: "Good",
    DEPLETED: "Depleted",
}


def parse_date(text) -> date:
    """Parse a YYYY-MM-DD string. Raises ValueError if the text is invalid."""
    return datetime.strptime(str(text).strip(), "%Y-%m-%d").date()


def days_until(expiry, today: date | None = None) -> int:
    """Days from today until the expiry date (negative if already expired)."""
    today = today or date.today()
    return (parse_date(expiry) - today).days


def expiry_status(expiry, today: date | None = None) -> str:
    """Classify an expiry date. A batch expiring today is still usable."""
    days = days_until(expiry, today)
    short, medium, long_ = config.EXPIRY_WINDOWS
    if days < 0:
        return EXPIRED
    if days <= short:
        return EXPIRING_30
    if days <= medium:
        return EXPIRING_60
    if days <= long_:
        return EXPIRING_90
    return OK


def stock_status(usable_stock: int, reorder_level: int) -> str:
    """Return OUT, LOW or OK for a medicine's usable (non-expired) stock."""
    if usable_stock <= 0:
        return "OUT"
    if usable_stock <= reorder_level:
        return "LOW"
    return "OK"
