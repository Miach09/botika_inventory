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


def test_add_medicine_can_be_cancelled(app, monkeypatch):
    med = app.tabs[1]
    fill(med, {"brand_name": "Biogesic", "generic_name": "acetaminophen"})
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    med.add()
    assert med.tree.get_children() == ()                 # nothing saved
    assert med.vars["brand_name"].get() == "Biogesic"    # form left as typed


def test_receive_stock_can_be_cancelled(app, service, monkeypatch):
    service.add_medicine({"brand_name": "Biogesic", "generic_name": "acetaminophen"})
    stock = app.tabs[2]
    stock.refresh()
    fill(stock, {"medicine": next(iter(stock.medicine_ids)), "batch_number": "B1",
                 "quantity": "40", "expiry_date": in_days(90)})
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    stock.receive()
    assert stock.tree.get_children() == ()
    assert stock.vars["batch_number"].get() == "B1"


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


def test_stock_sorting_by_batch_and_newest_first(app, service):
    mid = service.add_medicine({"brand_name": "Diatabs", "generic_name": "loperamide"})
    for number, received in (("B2", 5), ("B10", 3), ("B1", 1)):
        service.receive_batch({"medicine_id": mid, "batch_number": number, "quantity": "5",
                               "date_received": in_days(-received),
                               "expiry_date": in_days(100)})
    stock = app.tabs[2]
    stock.refresh()

    def batches():
        return [stock.tree.item(i, "values")[1] for i in stock.tree.get_children()]

    stock.sort_var.set("Newest batch first")
    stock._on_sort_preset()
    assert batches() == ["B1", "B10", "B2"]              # most recently received on top
    stock.sort_var.set("Oldest batch first")
    stock._on_sort_preset()
    assert batches() == ["B2", "B10", "B1"]
    stock.sort_by("batch")                               # heading click: natural A -> Z
    assert batches() == ["B1", "B2", "B10"]
    stock.sort_by("batch")                               # click again reverses
    assert batches() == ["B10", "B2", "B1"]


def test_dashboard_and_tab_switching(app, service):
    mid = service.add_medicine({"brand_name": "X", "generic_name": "g", "reorder_level": "50"})
    service.receive_batch({"medicine_id": mid, "batch_number": "1", "quantity": "5",
                           "expiry_date": in_days(5)})
    for i in range(len(app.tabs)):
        app.show(i)
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


def test_sidebar_navigation_and_out_of_stock_page(app, service):
    mid = service.add_medicine({"brand_name": "Empty", "generic_name": "g", "reorder_level": "5"})
    sup = service.add_supplier({"name": "MedSupply"})
    bid = service.receive_batch({"medicine_id": mid, "supplier_id": sup, "batch_number": "1",
                                 "quantity": "3", "expiry_date": in_days(100)})
    service.record_movement(bid, {"movement_type": "ISSUED", "quantity": "3"})
    app.show(3)                                     # Out of Stock page
    app.update()
    page = app.tabs[3]
    row = page.tree.item(page.tree.get_children()[0], "values")
    assert row[0] == "OUT" and row[1] == "Empty" and row[-1] == "MedSupply"
    assert app.sidebar.active == 3 and app.title_var.get().startswith("Out of Stock")


def test_sidebar_hover_does_not_redraw_forever_and_click_navigates(app):
    """Regression: hovering a menu item once caused an endless redraw loop (frozen window)."""
    import time
    paints = {"n": 0}
    original = app.sidebar._paint

    def counted():
        paints["n"] += 1
        return original()

    app.sidebar._paint = counted
    app.sidebar.event_generate("<Motion>", warp=True, x=100, y=96 + 2 * 46 + 19)
    end = time.time() + 0.4
    while time.time() < end:
        app.update()
    assert paints["n"] < 20
    app.sidebar.event_generate("<Button-1>", x=100, y=96 + 3 * 46 + 19)
    app.update()
    assert app.current == 3 and app.sidebar.active == 3


def _batch_with_long_reason(service):
    mid = service.add_medicine({"brand_name": "Ventolin", "generic_name": "albuterol",
                                "strength": "100 mcg"})
    bid = service.receive_batch({"medicine_id": mid, "batch_number": "VT-1", "quantity": "4",
                                 "expiry_date": in_days(200)})
    reason = ("New stock came in and we have a low stock currently on Ventolin so this "
              "adjustment was made after counting the shelf twice. " * 2).strip()[:195]
    service.record_movement(bid, {"movement_type": "ADJUST_IN", "quantity": "30", "reason": reason})
    return service.list_batches()[0], reason


def _center_info(window):
    """Measure where a window sits, using its OUTER frame (title bar and borders included).

    winfo_rootx/rooty give the client area; winfo_x/y give the outer top-left corner.
    """
    window.update()
    left, top = window.winfo_x(), window.winfo_y()
    border = window.winfo_rootx() - left          # side/bottom border width
    title = window.winfo_rooty() - top            # title bar height
    outer_w = window.winfo_width() + 2 * border
    outer_h = window.winfo_height() + title + border
    return {"dx": left + outer_w / 2 - window.winfo_screenwidth() / 2,
            "dy": top + outer_h / 2 - window.winfo_screenheight() / 2,
            "pos": (left, top), "client": (window.winfo_width(), window.winfo_height()),
            "border": border, "title": title,
            "screen": (window.winfo_screenwidth(), window.winfo_screenheight()),
            "geometry": window.geometry()}


def _centered(window, tolerance=40):
    info = _center_info(window)
    return abs(info["dx"]) <= tolerance and abs(info["dy"]) <= tolerance


def test_history_dialog_shows_close_button_full_reason_and_is_centered(app, service):
    from botika.gui.dialogs import HistoryDialog
    batch, reason = _batch_with_long_reason(service)
    dialog = HistoryDialog(app, service, batch)
    dialog.update()
    # the Close button is fully inside the window (not pushed out of view)
    button_bottom = dialog.close_button.winfo_rooty() + dialog.close_button.winfo_height()
    assert dialog.close_button.winfo_ismapped()
    assert button_bottom <= dialog.winfo_rooty() + dialog.winfo_height()
    # selecting a row shows the whole reason, even though the table cuts it off
    first = dialog.tree.get_children()[0]
    dialog.tree.selection_set(first)
    dialog.update()
    assert reason in dialog.detail_text.get("1.0", "end").replace("\n", " ")
    assert _centered(dialog), _center_info(dialog)
    dialog.destroy()


def test_movement_dialog_is_centered(app, service):
    from botika.gui.dialogs import MovementDialog
    batch, _ = _batch_with_long_reason(service)
    dialog = MovementDialog(app, service, batch)
    assert _centered(dialog), _center_info(dialog)
    dialog.destroy()


def test_main_window_starts_large(app):
    app.update()
    assert app.winfo_width() >= 1000 and app.winfo_height() >= 620      # never tiny, even on 1366x768


def test_top_bar_shows_date_and_live_time(app):
    import re
    text = app.clock_var.get()
    assert re.search(r"\d{4}   \|   \d{1,2}:\d{2}:\d{2} (AM|PM)$", text), text
    app._tick()                                   # a tick refreshes the text without errors
    assert re.search(r"\d{1,2}:\d{2}:\d{2} (AM|PM)$", app.clock_var.get())
