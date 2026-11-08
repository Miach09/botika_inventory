"""Medicines page: CRUD, search/filter, and the openFDA drug information lookup."""
import tkinter as tk
from tkinter import messagebox, ttk

from botika import config
from botika import validators
from botika.api_client import ApiError
from botika.gui import theme
from botika.gui.widgets import (Card, add_field, clear_table, guarded, make_table,
                                run_async, selected_id)

COLUMNS = [("brand", "Brand", 100, "w"), ("generic", "Generic", 100, "w"),
           ("strength", "Strength", 74, "w"), ("category", "Category", 105, "w"),
           ("stock", "Stock", 50, "e"), ("reorder", "Reorder", 68, "e"),
           ("status", "Status", 58, "center"), ("cost", "Cost", 56, "e")]
ALL_CATEGORIES = "All categories"


class MedicinesTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent)
        self.service, self.set_status = service, set_status
        self.selected = None
        self.category_ids = {}
        self.vars = {k: tk.StringVar() for k in (
            "brand_name", "generic_name", "strength", "dosage_form",
            "category", "reorder_level", "unit_cost")}
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value=ALL_CATEGORIES)
        self._build()
        self.clear_form()

    # ---- layout ------------------------------------------------------
    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        card = Card(self, "Medicine Details")
        card.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        form = card.body
        form.columnconfigure(1, weight=1)
        v = self.vars
        add_field(form, 0, "Brand name *", ttk.Entry(form, textvariable=v["brand_name"], width=20))
        add_field(form, 1, "Generic name *", ttk.Entry(form, textvariable=v["generic_name"]))
        add_field(form, 2, "Strength", ttk.Entry(form, textvariable=v["strength"]))
        add_field(form, 3, "Dosage form", ttk.Combobox(
            form, textvariable=v["dosage_form"], values=config.DOSAGE_FORMS))
        self.category_box = add_field(form, 4, "Category", ttk.Combobox(
            form, textvariable=v["category"], state="readonly"))
        add_field(form, 5, "Reorder level", ttk.Entry(form, textvariable=v["reorder_level"]))
        add_field(form, 6, "Unit cost (PHP)", ttk.Entry(form, textvariable=v["unit_cost"]))
        ttk.Label(form, style="Hint.TLabel", text=(
            "Use the U.S. generic name (for example\nacetaminophen) so the drug lookup works.")
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 12))

        buttons = ttk.Frame(form, style="Card.TFrame")
        buttons.grid(row=8, column=0, columnspan=2, sticky="ew")
        for i, (text, style, cmd) in enumerate([
                ("Add", "Success", self.add), ("Update", "Warning", self.update),
                ("Delete", "Danger", self.delete), ("Clear", "Secondary", self.clear_form)]):
            buttons.columnconfigure(i % 2, weight=1)
            button = ttk.Button(buttons, text=text, style=f"{style}.TButton", command=cmd)
            button.grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
            if style == "Danger" and not self.service.is_admin:
                button.state(["disabled"])            # only an admin may delete

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=2)

        listing = Card(right, "List of medicines", padding=10)
        listing.grid(row=0, column=0, sticky="nsew", pady=(0, 14))
        listing.body.columnconfigure(0, weight=1)
        listing.body.rowconfigure(1, weight=1)
        bar = ttk.Frame(listing.body, style="Card.TFrame")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(bar, text="Search:", style="Card.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=self.search_var, width=26).pack(side="left", padx=8)
        self.filter_box = ttk.Combobox(bar, textvariable=self.filter_var,
                                       state="readonly", width=24)
        self.filter_box.pack(side="left")
        self.search_var.trace_add("write", lambda *_: self.load_table())
        self.filter_box.bind("<<ComboboxSelected>>", lambda _e: self.load_table())
        frame, self.tree = make_table(listing.body, COLUMNS, height=8)
        frame.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        info = Card(right, "Drug Information (openFDA)", padding=10)
        info.grid(row=1, column=0, sticky="nsew")
        info.body.columnconfigure(0, weight=1)
        info.body.rowconfigure(1, weight=1)
        top = ttk.Frame(info.body, style="Card.TFrame")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.info_button = ttk.Button(top, text="Get Drug Info", style="Primary.TButton",
                                      command=self.get_drug_info)
        self.info_button.pack(side="left")
        self.info_label = ttk.Label(top, text="", style="Hint.TLabel")
        self.info_label.pack(side="left", padx=10)
        self.info_text = tk.Text(info.body, height=6, wrap="word", state="disabled",
                                 relief="flat", bg=theme.BG, fg=theme.TEXT, padx=10, pady=8,
                                 font=theme.font(10), highlightthickness=1,
                                 highlightbackground=theme.BORDER)
        scroll = ttk.Scrollbar(info.body, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=scroll.set)
        self.info_text.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")

    # ---- data --------------------------------------------------------
    def refresh(self):
        with guarded():
            cats = self.service.list_categories()
            self.category_ids = {c["name"]: c["id"] for c in cats}
            names = list(self.category_ids)
            self.category_box["values"] = names
            self.filter_box["values"] = [ALL_CATEGORIES] + names
            self.load_table()

    def load_table(self):
        with guarded():
            category_id = self.category_ids.get(self.filter_var.get())
            rows = self.service.list_medicines(self.search_var.get(), category_id)
            keep = self.selected
            clear_table(self.tree)
            for m in rows:
                tag = m["stock_status"] if m["stock_status"] != "OK" else ""
                self.tree.insert("", "end", iid=str(m["id"]), tags=(tag,), values=(
                    m["brand_name"], m["generic_name"], m["strength"],
                    m["category"] or "", m["usable_stock"], m["reorder_level"],
                    m["stock_status"], f"{m['unit_cost']:.2f}"))
            if keep is not None and self.tree.exists(str(keep)):
                self.tree.selection_set(str(keep))
            self.set_status(f"{len(rows)} medicine(s) shown.")

    def _raw(self):
        raw = {k: v.get() for k, v in self.vars.items()}
        raw["category_id"] = self.category_ids.get(raw.pop("category"))
        return raw

    # ---- actions -----------------------------------------------------
    def add(self):
        with guarded():
            raw = self._raw()
            data = validators.validate_medicine(raw)      # show input errors first
            detail = f"{data['brand_name']} ({data['generic_name']})"
            if data.get("strength"):
                detail += f", {data['strength']}"
            if not messagebox.askyesno("Confirm add", f"Add this medicine?\n\n{detail}"):
                return
            self.service.add_medicine(raw)
            self.clear_form()
            self.load_table()
            messagebox.showinfo("Saved", "Medicine added successfully.")
            self.set_status("Medicine added.")

    def update(self):
        if self.selected is None:
            messagebox.showwarning("No selection", "Select a medicine in the table first.")
            return
        with guarded():
            self.service.update_medicine(self.selected, self._raw())
            self.load_table()
            messagebox.showinfo("Saved", "Medicine updated successfully.")
            self.set_status("Medicine updated.")

    def delete(self):
        if self.selected is None:
            messagebox.showwarning("No selection", "Select a medicine in the table first.")
            return
        name = self.vars["brand_name"].get()
        if not messagebox.askyesno("Confirm delete",
                                   f"Delete '{name}'? This cannot be undone."):
            return
        with guarded():
            self.service.delete_medicine(self.selected)
            self.clear_form()
            self.load_table()
            self.set_status("Medicine deleted.")

    def clear_form(self):
        self.selected = None
        for var in self.vars.values():
            var.set("")
        self.vars["reorder_level"].set(str(config.DEFAULT_REORDER_LEVEL))
        self.vars["unit_cost"].set("0")
        if hasattr(self, "tree"):
            self.tree.selection_remove(self.tree.selection())
        self.show_info("Select a medicine, then click 'Get Drug Info'.", "")

    def on_select(self, _event=None):
        mid = selected_id(self.tree)
        if mid is None:
            return
        with guarded():
            row = next((m for m in self.service.list_medicines() if m["id"] == mid), None)
            if row is None:
                return
            self.selected = mid
            for key in ("brand_name", "generic_name", "strength", "dosage_form"):
                self.vars[key].set(row[key])
            self.vars["category"].set(row["category"] or "")
            self.vars["reorder_level"].set(str(row["reorder_level"]))
            self.vars["unit_cost"].set(f"{row['unit_cost']:.2f}")
            if row["drug_info"]:
                self.show_info(row["drug_info"], f"Saved on {row['drug_info_fetched']}")
            else:
                self.show_info("No drug information saved yet. Click 'Get Drug Info'.", "")

    # ---- REST API lookup ---------------------------------------------
    def show_info(self, text, note):
        self.info_label.configure(text=note)
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", text)
        self.info_text.configure(state="disabled")

    def get_drug_info(self):
        if self.selected is None:
            messagebox.showwarning("No selection", "Select a medicine in the table first.")
            return
        medicine_id = self.selected
        generic = self.vars["generic_name"].get().strip()
        self.info_button.configure(state="disabled")
        self.show_info("Contacting openFDA...", "")
        self.set_status(f"Looking up '{generic}' ...")
        run_async(self, lambda: self.service.lookup_drug_info(generic),
                  lambda info: self._info_ok(medicine_id, info), self._info_failed)

    def _info_ok(self, medicine_id, info):
        self.info_button.configure(state="normal")
        with guarded():
            self.service.save_drug_info(medicine_id, info)
            if self.selected == medicine_id:
                self.show_info(info.to_text(), "Retrieved just now")
            self.set_status("Drug information retrieved and saved.")

    def _info_failed(self, exc):
        self.info_button.configure(state="normal")
        self.show_info("Drug information could not be retrieved.", "")
        self.set_status("Drug lookup failed.")
        if isinstance(exc, ApiError):
            messagebox.showwarning("Drug information unavailable", str(exc))
        else:
            messagebox.showerror("Unexpected error", str(exc))
