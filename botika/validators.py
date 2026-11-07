"""Input validation. Every function returns cleaned data or raises ValidationError."""
import re
from datetime import date

from botika import config
from botika.rules import parse_date

PHONE_RE = re.compile(r"^[0-9+()\-\s]{7,20}$")
BATCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_/]{0,49}$")


class ValidationError(Exception):
    """Raised when user input is invalid. `errors` holds one message per problem."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _int(value, label, errors, minimum=None, required=True, default=None):
    raw = _text(value)
    if raw == "":
        if required and default is None:
            errors.append(f"{label} is required.")
        return default
    try:
        number = int(raw)
    except ValueError:
        errors.append(f"{label} must be a whole number.")
        return None
    if minimum is not None and number < minimum:
        errors.append(f"{label} must be at least {minimum}.")
        return None
    return number


def _date(value, label, errors, required=True):
    raw = _text(value)
    if raw == "":
        if required:
            errors.append(f"{label} is required (format YYYY-MM-DD).")
        return None
    try:
        return parse_date(raw)
    except ValueError:
        errors.append(f"{label} must be a valid date in the format YYYY-MM-DD.")
        return None


def validate_medicine(raw: dict) -> dict:
    errors = []
    brand = _text(raw.get("brand_name"))
    generic = _text(raw.get("generic_name"))
    strength = _text(raw.get("strength"))
    form = _text(raw.get("dosage_form"))

    if not brand:
        errors.append("Brand name is required.")
    elif len(brand) > 100:
        errors.append("Brand name must be 100 characters or fewer.")
    if not generic:
        errors.append("Generic name is required (it is used for the drug lookup).")
    elif len(generic) > 100:
        errors.append("Generic name must be 100 characters or fewer.")
    elif '"' in generic:
        errors.append("Generic name must not contain double quotes.")
    if len(strength) > 30:
        errors.append("Strength must be 30 characters or fewer.")
    if len(form) > 30:
        errors.append("Dosage form must be 30 characters or fewer.")

    category_id = _int(raw.get("category_id"), "Category", errors, required=False)
    reorder = _int(raw.get("reorder_level"), "Reorder level", errors,
                   minimum=0, default=config.DEFAULT_REORDER_LEVEL)

    cost_raw = _text(raw.get("unit_cost"))
    cost = 0.0
    if cost_raw:
        try:
            cost = float(cost_raw)
            if cost < 0:
                errors.append("Unit cost cannot be negative.")
        except ValueError:
            errors.append("Unit cost must be a number.")

    if errors:
        raise ValidationError(errors)
    return {
        "brand_name": brand, "generic_name": generic, "strength": strength,
        "dosage_form": form, "category_id": category_id,
        "reorder_level": reorder, "unit_cost": round(cost, 2),
    }


def validate_supplier(raw: dict) -> dict:
    errors = []
    name = _text(raw.get("name"))
    contact = _text(raw.get("contact_number"))
    address = _text(raw.get("address"))
    if not name:
        errors.append("Supplier name is required.")
    elif len(name) > 100:
        errors.append("Supplier name must be 100 characters or fewer.")
    if contact and not PHONE_RE.match(contact):
        errors.append("Contact number may only contain digits, spaces, + ( ) and -, "
                      "and must be 7 to 20 characters.")
    if len(address) > 200:
        errors.append("Address must be 200 characters or fewer.")
    if errors:
        raise ValidationError(errors)
    return {"name": name, "contact_number": contact, "address": address}


def validate_batch(raw: dict, creating: bool = True, today: date | None = None) -> dict:
    today = today or date.today()
    errors = []
    medicine_id = _int(raw.get("medicine_id"), "Medicine", errors)
    supplier_id = _int(raw.get("supplier_id"), "Supplier", errors, required=False)

    batch_number = _text(raw.get("batch_number"))
    if not batch_number:
        errors.append("Batch number is required.")
    elif not BATCH_RE.match(batch_number):
        errors.append("Batch number may only contain letters, digits, - _ / (max 50).")

    quantity = None
    if creating:
        quantity = _int(raw.get("quantity"), "Quantity", errors, minimum=1)

    received = _date(raw.get("date_received") or today.isoformat(),
                     "Date received", errors)
    expiry = _date(raw.get("expiry_date"), "Expiry date", errors)

    if received and received > today:
        errors.append("Date received cannot be in the future.")
    if received and expiry:
        if expiry <= received:
            errors.append("Expiry date must be after the date received.")
        elif creating and expiry < today:
            errors.append("This batch is already expired and cannot be received.")

    if errors:
        raise ValidationError(errors)
    data = {
        "medicine_id": medicine_id, "supplier_id": supplier_id,
        "batch_number": batch_number,
        "date_received": received.isoformat(), "expiry_date": expiry.isoformat(),
    }
    if creating:
        data["quantity"] = quantity
    return data


def validate_movement(raw: dict) -> dict:
    errors = []
    mtype = _text(raw.get("movement_type"))
    if mtype not in config.MOVEMENT_SIGNS or mtype == "RECEIVED":
        errors.append("Please choose a movement type.")
    quantity = _int(raw.get("quantity"), "Quantity", errors, minimum=1)
    reason = _text(raw.get("reason"))
    if len(reason) > 200:
        errors.append("Reason must be 200 characters or fewer.")
    if mtype in config.REASON_REQUIRED and not reason:
        errors.append("A reason is required for this movement type.")
    if errors:
        raise ValidationError(errors)
    return {"movement_type": mtype, "quantity": quantity, "reason": reason}
