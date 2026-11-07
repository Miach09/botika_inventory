"""Stock tab: receive batches, track expiry, issue or adjust stock."""
from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk

from botika.gui.dialogs import HistoryDialog, MovementDialog
from botika.gui.widgets import (add_field, clear_table, guarded, make_table,
                                selected_id)
from botika.services import BATCH_FILTERS

NO_SUPPLIER = "(none)"
COLUMNS = [("medicine", "Medicine", 130, "w"), ("batch", "Batch No.", 75, "w"),
           ("qty", "Qty", 40, "e"), ("received", "Received", 92, "center"),
           ("expiry", "Expiry", 92, "center"), ("days", "Days", 45, "e"),
           ("status", "Status", 115, "w"), ("supplier", "Supplier", 100, "w")]


class StockTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent, padding=8)
        self.service, self.set_status = service, set_status
        self.selected = None
        self.medicine_ids, self.medicine_labels = {}, {}
        self.supplier_ids, self.supplier_labels = {NO_SUPPLIER: None}, {None: NO_SUPPLIER}
        self.batches = {}
        self.vars = {k: tk.StringVar() for k in (
            "medicine", "supplier", "batch_number", "quantity",
            "date_received", "expiry_date")}
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value=BATCH_FILTERS["ALL"])
        self.filter_keys = {label: key for key, label in BATCH_FILTERS.items()}
        self._build()
        self.clear_form()

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        form = ttk.LabelFrame(self, text="Stock Batch", padding=10)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        form.columnconfigure(1, weight=1)
        v = self.vars
        self.medicine_box = add_field(form, 0, "Medicine *", ttk.Combobox(
            form, textvariable=v["medicine"], state="readonly", width=26))
        self.supplier_box = add_field(form, 1, "Supplier", ttk.Combobox(
            form, textvariable=v["supplier"], state="readonly"))
        add_field(form, 2, "Batch number *", ttk.Entry(form, textvariable=v["batch_number"]))
        self.qty_entry = add_field(form, 3, "Quantity *", ttk.Entry(form, textvariable=v["quantity"]))
        add_field(form, 4, "Date received", ttk.Entry(form, textvariable=v["date_received"]))
        add_field(form, 5, "Expiry date *", ttk.Entry(form, textvariable=v["expiry_date"]))
        ttk.Label(form, text="Dates use YYYY-MM-DD. Quantity of an existing batch\n"
                             "is changed with 'Issue / Adjust Stock'.",
                  foreground="#666").grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 8))
        buttons = ttk.Frame(form)
        buttons.grid(row=7, column=0, columnspan=2, sticky="ew")
        for i, (text, cmd) in enumerate([("Receive Stock", self.receive),
                                         ("Update Batch", self.update),
                                         ("Delete Batch", self.delete),
                                         ("Clear", self.clear_form)]):
            buttons.columnconfigure(i % 2, weight=1)
            ttk.Button(buttons, text=text, command=cmd).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        bar = ttk.Frame(right)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side="left")
        ttk.Entry(bar, textvariable=self.search_var, width=24).pack(side="left", padx=6)
        self.filter_box = ttk.Combobox(bar, textvariable=self.filter_var, state="readonly",
                                       values=list(BATCH_FILTERS.values()), width=26)
        self.filter_box.pack(side="left")
        self.search_var.trace_add("write", lambda *_: self.load_table())
        self.filter_box.bind("<<ComboboxSelected>>", lambda _e: self.load_table())

        frame, self.tree = make_table(right, COLUMNS, height=14)
        frame.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        actions = ttk.Frame(right)
        actions.grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Button(actions, text="Issue / Adjust Stock", command=self.adjust).pack(side="left")
        ttk.Button(actions, text="View History", command=self.history).pack(side="left", padx=6)

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

    def load_table(self):
        with guarded():
            key = self.filter_keys.get(self.filter_var.get(), "ALL")
            rows = self.service.list_batches(self.search_var.get(), key)
            self.batches = {b["id"]: b for b in rows}
            keep = self.selected
            clear_table(self.tree)
            for b in rows:
                tag = b["status"] if b["status"] != "OK" else ""
                name = f"{b['brand_name']} {b['strength']}".strip()
                self.tree.insert("", "end", iid=str(b["id"]), tags=(tag,), values=(
                    name, b["batch_number"], b["quantity"], b["date_received"],
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
            self.service.receive_batch(self._raw())
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
