"""GUI smoke test: builds the real window and drives the main workflows.

Skipped automatically when no display is available.
Run on a headless machine with:  xvfb-run -a python -m pytest tests/test_gui_smoke.py
"""
import os
import sys

import pytest

tk = pytest.importorskip("tkinter")
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    pytest.skip("no display available", allow_module_level=True)

from tkinter import messagebox  # noqa: E402

from botika.api_client import ApiNoResultsError, DrugInfo  # noqa: E402
from botika.gui.app import BotikaApp  # noqa: E402
from tests.conftest import in_days  # noqa: E402


@pytest.fixture
def app(service, monkeypatch):
    shown = []
    for name in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(messagebox, name, lambda t, m, _n=name, **k: shown.append((_n, t, m)))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    try:
        window = BotikaApp(service)
    except tk.TclError:
        pytest.skip("Tk could not open a display")
    window.shown = shown
    window.update()
    yield window
    window.destroy()


def fill(tab, values):
    for key, value in values.items():
        tab.vars[key].set(value)


def test_add_medicine_through_form_and_validation_message(app):
    med = app.tabs[1]
    med.add()                                            # empty form
    assert app.shown[-1][0] == "showwarning" and "Brand name is required" in app.shown[-1][2]
    fill(med, {"brand_name": "Biogesic", "generic_name": "acetaminophen",
               "strength": "500 mg", "dosage_form": "Tablet"})
    med.add()
    assert app.shown[-1][0] == "showinfo"
    assert len(med.tree.get_children()) == 1


def test_update_delete_and_search(app):
    med = app.tabs[1]
    fill(med, {"brand_name": "A", "generic_name": "g1"})
    med.add()
    fill(med, {"brand_name": "B", "generic_name": "g2"})
    med.add()
    med.search_var.set("B")
    app.update()
    assert len(med.tree.get_children()) == 1
    med.tree.selection_set(med.tree.get_children()[0])
    app.update()
    med.vars["brand_name"].set("B2")
    med.update()
    assert med.tree.item(med.tree.get_children()[0], "values")[0] == "B2"
    med.delete()
    assert med.tree.get_children() == ()


def test_receive_stock_and_issue(app, service):
    mid = service.add_medicine({"brand_name": "Biogesic", "generic_name": "acetaminophen",
                                "strength": "500 mg", "dosage_form": "Tablet"})
    stock = app.tabs[2]
    stock.refresh()
    label = next(iter(stock.medicine_ids))
    fill(stock, {"medicine": label, "batch_number": "B1", "quantity": "40",
                 "expiry_date": in_days(10)})
    stock.receive()
    assert app.shown[-1][0] == "showinfo"
    row = stock.tree.get_children()[0]
    assert stock.tree.item(row, "values")[2] == "40"
    assert "EXPIRING_30" in stock.tree.item(row, "tags")
    service.record_movement(int(row), {"movement_type": "ISSUED", "quantity": "5"})
    stock.load_table()
    assert stock.tree.item(row, "values")[2] == "35"


def test_dashboard_and_tab_switching(app, service):
    mid = service.add_medicine({"brand_name": "X", "generic_name": "g", "reorder_level": "50"})
    service.receive_batch({"medicine_id": mid, "batch_number": "1", "quantity": "5",
                           "expiry_date": in_days(5)})
    for i in range(len(app.tabs)):
        app.notebook.select(i)
        app.update()
    dash = app.tabs[0]
    dash.refresh()
    assert dash.vars["expiring_30"].get() == "1"
    assert len(dash.tree.get_children()) >= 2       # expiring + low stock


def test_drug_info_success_and_failure_paths(app, service):
    mid = service.add_medicine({"brand_name": "X", "generic_name": "ibuprofen"})
    med = app.tabs[1]
    med.refresh()
    med.tree.selection_set(str(mid))
    app.update()
    med._info_ok(mid, DrugInfo("ibuprofen", indications="Pain relief."))
    assert "Pain relief" in med.info_text.get("1.0", "end")
    assert service.list_medicines()[0]["drug_info"]
    med._info_failed(ApiNoResultsError("No drug label was found."))
    assert app.shown[-1][0] == "showwarning"
    assert str(med.info_button.cget("state")) == "normal"
