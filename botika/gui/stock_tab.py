"""Stock Batches page: receive batches, track expiry, issue or adjust stock."""
from datetime import date
import re
import tkinter as tk
from tkinter import messagebox, ttk

from botika import validators
from botika.gui.dialogs import HistoryDialog, MovementDialog
from botika.gui.widgets import (Card, add_field, clear_table, guarded, make_table,
                                selected_id)
from botika.services import BATCH_FILTERS

NO_SUPPLIER = "(none)"
COLUMNS = [("medicine", "Medicine", 118, "w"), ("batch", "Batch No.", 74, "w"),
           ("qty", "Qty", 36, "e"), ("expiry", "Expiry", 84, "center"),
           ("days", "Days", 40, "e"), ("status", "Status", 98, "w"),
           ("supplier", "Supplier", 120, "w")]


# Sort presets shown in the "Sort" box: label -> (column key, descending?)
SORT_PRESETS = {
    "Expiry date (soonest first)": ("expiry", False),
    "Newest batch first": ("received", True),
    "Oldest batch first": ("received", False),
}
COLUMN_TITLES = {key: title for key, title, _w, _a in COLUMNS}


def _natural(text):
    """Sort 'B2' before 'B10' by comparing the number parts as numbers."""
    return [(0, int(p), "") if p.isdigit() else (1, 0, p.lower())
            for p in re.split(r"(\d+)", str(text)) if p != ""]


SORT_KEYS = {
    "medicine": lambda b: f"{b['brand_name']} {b['strength']}".strip().lower(),
    "batch": lambda b: _natural(b["batch_number"]),
    "qty": lambda b: b["quantity"],
    "expiry": lambda b: b["expiry_date"],
    "days": lambda b: b["days_left"],
    "status": lambda b: b["status_label"],
    "supplier": lambda b: (b["supplier"] or "").lower(),
    # date received, then entry order, so batches received the same day stay in order
    "received": lambda b: (b["date_received"], b["id"]),
}


class StockTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent)
        self.service, self.set_status = service, set_status
        self.selected = None
        self.medicine_ids, self.medicine_labels = {}, {}
        self.supplier_ids, self.supplier_labels = {NO_SUPPLIER: None}, {None: NO_SUPPLIER}
        self.batches = {}
        self.vars = {k: tk.StringVar() for k in (
            "medicine", "supplier", "batch_number", "quantity",
            "date_received", "expiry_date")}
        self.search_var = tk.StringVar()
        self.sort_var = tk.StringVar(value=next(iter(SORT_PRESETS)))
        self.sort_key, self.sort_desc = SORT_PRESETS[self.sort_var.get()]
        self.filter_var = tk.StringVar(value=BATCH_FILTERS["ALL"])
        self.filter_keys = {label: key for key, label in BATCH_FILTERS.items()}
        self._build()
        self.clear_form()

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        card = Card(self, "Stock Batch")
        card.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        form = card.body
        form.columnconfigure(1, weight=1)
        v = self.vars
        self.medicine_box = add_field(form, 0, "Medicine *", ttk.Combobox(
            form, textvariable=v["medicine"], state="readonly", width=20))
        self.supplier_box = add_field(form, 1, "Supplier", ttk.Combobox(
            form, textvariable=v["supplier"], state="readonly"))
        add_field(form, 2, "Batch number *", ttk.Entry(form, textvariable=v["batch_number"]))
        self.qty_entry = add_field(form, 3, "Quantity *", ttk.Entry(form, textvariable=v["quantity"]))
        add_field(form, 4, "Date received", ttk.Entry(form, textvariable=v["date_received"]))
        add_field(form, 5, "Expiry date *", ttk.Entry(form, textvariable=v["expiry_date"]))
        ttk.Label(form, style="Hint.TLabel", text=(
            "Dates use YYYY-MM-DD. The quantity of an existing\n"
            "batch is changed with 'Issue / Adjust Stock'.")
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 12))
        buttons = ttk.Frame(form, style="Card.TFrame")
        buttons.grid(row=7, column=0, columnspan=2, sticky="ew")
        for i, (text, style, cmd) in enumerate([
                ("Receive Stock", "Success", self.receive), ("Update Batch", "Warning", self.update),
                ("Delete Batch", "Danger", self.delete), ("Clear", "Secondary", self.clear_form)]):
            buttons.columnconfigure(i % 2, weight=1)
            ttk.Button(buttons, text=text, style=f"{style}.TButton", command=cmd).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)

        listing = Card(self, "List of stock batches", padding=10)
        listing.grid(row=0, column=1, sticky="nsew")
        listing.body.columnconfigure(0, weight=1)
        listing.body.rowconfigure(1, weight=1)
        bar = ttk.Frame(listing.body, style="Card.TFrame")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(bar, text="Search:", style="Card.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=self.search_var, width=22).pack(side="left", padx=8)
        self.filter_box = ttk.Combobox(bar, textvariable=self.filter_var, state="readonly",
                                       values=list(BATCH_FILTERS.values()), width=26)
        self.filter_box.pack(side="left")
        ttk.Label(bar, text="Sort:", style="Card.TLabel").pack(side="left", padx=(12, 6))
        self.sort_box = ttk.Combobox(bar, textvariable=self.sort_var, state="readonly",
                                     values=list(SORT_PRESETS), width=24)
        self.sort_box.pack(side="left")
        self.sort_box.bind("<<ComboboxSelected>>", self._on_sort_preset)
        self.search_var.trace_add("write", lambda *_: self.load_table())
        self.filter_box.bind("<<ComboboxSelected>>", lambda _e: self.load_table())

        frame, self.tree = make_table(listing.body, COLUMNS, height=14)
        frame.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        for key in COLUMN_TITLES:                     # click a heading to sort by it
            self.tree.heading(key, command=lambda k=key: self.sort_by(k))
        self._update_headings()

        actions = ttk.Frame(listing.body, style="Card.TFrame")
        actions.grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(actions, text="Issue / Adjust Stock", style="Primary.TButton",
                   command=self.adjust).pack(side="left")
        ttk.Button(actions, text="View History", style="Secondary.TButton",
                   command=self.history).pack(side="left", padx=8)

    # ---- data --------------------------------------------------------
    def refresh(self):
        with guarded():
            meds = self.service.list_medicines()
            self.medicine_ids, self.medicine_labels = {}, {}
            for m in meds:
                label = " ".join(p for p in (m["brand_name"], m["strength"],
                                             m["dosage_form"]) if p)
                label = f"{label} - {m['generic_name']}"
                self.medicine_ids[label] = m["id"]
                self.medicine_labels[m["id"]] = label
            self.medicine_box["values"] = list(self.medicine_ids)
            sups = self.service.list_suppliers()
            self.supplier_ids = {NO_SUPPLIER: None}
            self.supplier_labels = {None: NO_SUPPLIER}
            for s in sups:
                self.supplier_ids[s["name"]] = s["id"]
                self.supplier_labels[s["id"]] = s["name"]
            self.supplier_box["values"] = list(self.supplier_ids)
            self.load_table()

    # ---- sorting -----------------------------------------------------
    def _on_sort_preset(self, _event=None):
        self.sort_key, self.sort_desc = SORT_PRESETS[self.sort_var.get()]
        self._update_headings()
        self.load_table()

    def sort_by(self, column):
        """Heading click: sort by that column; clicking again reverses the order."""
        if column == self.sort_key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key, self.sort_desc = column, False
        preset = next((label for label, spec in SORT_PRESETS.items()
                       if spec == (self.sort_key, self.sort_desc)), "Sorted by column heading")
        self.sort_var.set(preset)
        self._update_headings()
        self.load_table()

    def _update_headings(self):
        for key, title in COLUMN_TITLES.items():
            arrow = ""
            if key == self.sort_key:
                arrow = " \u25bc" if self.sort_desc else " \u25b2"
            self.tree.heading(key, text=title + arrow)

    def _sorted(self, rows):
        return sorted(rows, key=SORT_KEYS[self.sort_key], reverse=self.sort_desc)

    def load_table(self):
        with guarded():
            key = self.filter_keys.get(self.filter_var.get(), "ALL")
            rows = self._sorted(self.service.list_batches(self.search_var.get(), key))
            self.batches = {b["id"]: b for b in rows}
            keep = self.selected
            clear_table(self.tree)
            for b in rows:
                tag = b["status"] if b["status"] != "OK" else ""
                name = f"{b['brand_name']} {b['strength']}".strip()
                self.tree.insert("", "end", iid=str(b["id"]), tags=(tag,), values=(
                    name, b["batch_number"], b["quantity"],
                    b["expiry_date"], b["days_left"], b["status_label"],
                    b["supplier"] or ""))
            if keep is not None and self.tree.exists(str(keep)):
                self.tree.selection_set(str(keep))
            self.set_status(f"{len(rows)} batch(es) shown.")

    def _raw(self):
        return {
            "medicine_id": self.medicine_ids.get(self.vars["medicine"].get()),
            "supplier_id": self.supplier_ids.get(self.vars["supplier"].get()),
            "batch_number": self.vars["batch_number"].get(),
            "quantity": self.vars["quantity"].get(),
            "date_received": self.vars["date_received"].get(),
            "expiry_date": self.vars["expiry_date"].get(),
        }

    # ---- actions -----------------------------------------------------
    def receive(self):
        with guarded():
            raw = self._raw()
            data = validators.validate_batch(raw, creating=True)   # show input errors first
            medicine = self.vars["medicine"].get()
            if not messagebox.askyesno(
                    "Confirm receive stock",
                    f"Receive this stock?\n\nMedicine: {medicine}\n"
                    f"Batch no.: {data['batch_number']}\n"
                    f"Quantity: {data['quantity']}\n"
                    f"Expiry: {raw['expiry_date'].strip()}"):
                return
            self.service.receive_batch(raw)
            self.clear_form()
            self.load_table()
            messagebox.showinfo("Saved", "Stock received successfully.")

    def update(self):
        if self.selected is None:
            messagebox.showwarning("No selection", "Select a batch in the table first.")
            return
        with guarded():
            self.service.update_batch(self.selected, self._raw())
            self.load_table()
            messagebox.showinfo("Saved", "Batch updated successfully.")

    def delete(self):
        if self.selected is None:
            messagebox.showwarning("No selection", "Select a batch in the table first.")
            return
        if not messagebox.askyesno("Confirm delete",
                                   "Delete this batch and its movement history?\n"
                                   "This cannot be undone."):
            return
        with guarded():
            self.service.delete_batch(self.selected)
            self.clear_form()
            self.load_table()

    def clear_form(self):
        self.selected = None
        for var in self.vars.values():
            var.set("")
        self.vars["supplier"].set(NO_SUPPLIER)
        self.vars["date_received"].set(date.today().isoformat())
        self.qty_entry.configure(state="normal")
        if hasattr(self, "tree"):
            self.tree.selection_remove(self.tree.selection())

    def on_select(self, _event=None):
        bid = selected_id(self.tree)
        batch = self.batches.get(bid)
        if batch is None:
            return
        self.selected = bid
        self.vars["medicine"].set(self.medicine_labels.get(batch["medicine_id"], ""))
        self.vars["supplier"].set(self.supplier_labels.get(batch["supplier_id"], NO_SUPPLIER))
        self.vars["batch_number"].set(batch["batch_number"])
        self.vars["date_received"].set(batch["date_received"])
        self.vars["expiry_date"].set(batch["expiry_date"])
        self.vars["quantity"].set(str(batch["quantity"]))
        self.qty_entry.configure(state="disabled")

    def _selected_batch(self):
        batch = self.batches.get(self.selected)
        if batch is None:
            messagebox.showwarning("No selection", "Select a batch in the table first.")
        return batch

    def adjust(self):
        batch = self._selected_batch()
        if batch is None:
            return
        dialog = MovementDialog(self, self.service, batch)
        self.wait_window(dialog)
        if dialog.changed:
            self.load_table()
            self.set_status("Stock updated.")

    def history(self):
        batch = self._selected_batch()
        if batch is not None:
            HistoryDialog(self, self.service, batch)
