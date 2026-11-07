"""Suppliers tab: CRUD with search."""
import tkinter as tk
from tkinter import messagebox, ttk

from botika.gui.widgets import add_field, clear_table, guarded, make_table, selected_id

COLUMNS = [("name", "Supplier", 220, "w"), ("contact", "Contact number", 140, "w"),
           ("address", "Address", 380, "w")]


class SuppliersTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent, padding=8)
        self.service, self.set_status = service, set_status
        self.selected = None
        self.vars = {k: tk.StringVar() for k in ("name", "contact_number", "address")}
        self.search_var = tk.StringVar()
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        form = ttk.LabelFrame(self, text="Supplier Details", padding=10)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        form.columnconfigure(1, weight=1)
        add_field(form, 0, "Name *", ttk.Entry(form, textvariable=self.vars["name"], width=28))
        add_field(form, 1, "Contact number", ttk.Entry(form, textvariable=self.vars["contact_number"]))
        add_field(form, 2, "Address", ttk.Entry(form, textvariable=self.vars["address"]))
        buttons = ttk.Frame(form)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for i, (text, cmd) in enumerate([("Add", self.add), ("Update", self.update),
                                         ("Delete", self.delete), ("Clear", self.clear_form)]):
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
        ttk.Entry(bar, textvariable=self.search_var, width=30).pack(side="left", padx=6)
        self.search_var.trace_add("write", lambda *_: self.refresh())
        frame, self.tree = make_table(right, COLUMNS, height=14)
        frame.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def refresh(self):
        with guarded():
            rows = self.service.list_suppliers(self.search_var.get())
            clear_table(self.tree)
            for s in rows:
                self.tree.insert("", "end", iid=str(s["id"]),
                                 values=(s["name"], s["contact_number"], s["address"]))
            self.set_status(f"{len(rows)} supplier(s) shown.")

    def on_select(self, _event=None):
        sid = selected_id(self.tree)
        if sid is None:
            return
        name, contact, address = self.tree.item(str(sid), "values")
        self.selected = sid
        self.vars["name"].set(name)
        self.vars["contact_number"].set(contact)
        self.vars["address"].set(address)

    def clear_form(self):
        self.selected = None
        for var in self.vars.values():
            var.set("")
        self.tree.selection_remove(self.tree.selection())

    def _raw(self):
        return {k: v.get() for k, v in self.vars.items()}

    def add(self):
        with guarded():
            self.service.add_supplier(self._raw())
            self.clear_form()
            self.refresh()
            messagebox.showinfo("Saved", "Supplier added successfully.")

    def update(self):
        if self.selected is None:
            messagebox.showwarning("No selection", "Select a supplier in the table first.")
            return
        with guarded():
            self.service.update_supplier(self.selected, self._raw())
            self.refresh()
            messagebox.showinfo("Saved", "Supplier updated successfully.")

    def delete(self):
        if self.selected is None:
            messagebox.showwarning("No selection", "Select a supplier in the table first.")
            return
        if not messagebox.askyesno("Confirm delete",
                                   f"Delete '{self.vars['name'].get()}'?\n"
                                   "Existing batches keep their records without a supplier."):
            return
        with guarded():
            self.service.delete_supplier(self.selected)
            self.clear_form()
            self.refresh()
