"""Reports tab: CSV export and import (file management)."""
from datetime import date
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from botika import config
from botika.gui.widgets import guarded


class ReportsTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent, padding=12)
        self.service, self.set_status = service, set_status
        self.days_var = tk.StringVar(value="90")

        export = ttk.LabelFrame(self, text="Export to CSV", padding=10)
        export.pack(fill="x")
        for i, (text, cmd) in enumerate([
                ("Medicines & stock levels", self.export_medicines),
                ("All stock batches", self.export_batches),
                ("Stock movement history", self.export_movements)]):
            ttk.Button(export, text=text, command=cmd, width=28).grid(
                row=0, column=i, padx=4, pady=4)
        row = ttk.Frame(export)
        row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(row, text="Expiry report: expired items and those expiring within").pack(side="left")
        ttk.Combobox(row, textvariable=self.days_var, width=5, state="readonly",
                     values=[str(d) for d in config.EXPIRY_WINDOWS]).pack(side="left", padx=6)
        ttk.Label(row, text="days").pack(side="left")
        ttk.Button(row, text="Export expiry report", command=self.export_expiry).pack(
            side="left", padx=10)

        importer = ttk.LabelFrame(self, text="Import medicines from CSV", padding=10)
        importer.pack(fill="x", pady=12)
        ttk.Label(importer, text="Required columns: brand_name, generic_name. Optional: "
                  "strength, dosage_form, category, reorder_level, unit_cost.").pack(anchor="w")
        buttons = ttk.Frame(importer)
        buttons.pack(anchor="w", pady=(8, 0))
        ttk.Button(buttons, text="Save blank template...", command=self.save_template).pack(side="left")
        ttk.Button(buttons, text="Import CSV file...", command=self.import_csv).pack(side="left", padx=8)

        ttk.Label(self, text="Activity").pack(anchor="w")
        self.log = tk.Text(self, height=12, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    def refresh(self):
        pass  # nothing to reload; kept so every tab has the same interface

    def _write_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.set_status(message)

    def _ask_save(self, default_name):
        config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        return filedialog.asksaveasfilename(
            title="Save CSV file", defaultextension=".csv",
            initialdir=str(config.EXPORT_DIR), initialfile=default_name,
            filetypes=[("CSV files", "*.csv")])

    def _export(self, default_name, func, noun):
        path = self._ask_save(f"{default_name}_{date.today().isoformat()}.csv")
        if not path:
            return
        with guarded():
            count = func(path)
            self._write_log(f"Exported {count} {noun} to {path}")
            messagebox.showinfo("Export complete", f"Exported {count} {noun}.")

    def export_medicines(self):
        self._export("medicines", self.service.export_medicines, "medicine(s)")

    def export_batches(self):
        self._export("stock_batches", self.service.export_batches, "batch(es)")

    def export_movements(self):
        self._export("stock_movements", self.service.export_movements, "movement(s)")

    def export_expiry(self):
        days = int(self.days_var.get())
        self._export(f"expiry_report_{days}d",
                     lambda p: self.service.export_expiry_report(p, days), "batch(es)")

    def save_template(self):
        path = self._ask_save("medicines_import_template.csv")
        if path:
            with guarded():
                self.service.write_import_template(path)
                self._write_log(f"Saved import template to {path}")

    def import_csv(self):
        path = filedialog.askopenfilename(title="Choose a CSV file",
                                          filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        with guarded():
            added, skipped, errors = self.service.import_medicines(path)
            self._write_log(f"Import finished: {added} added, {skipped} skipped.")
            for err in errors[:20]:
                self._write_log("  - " + err)
            messagebox.showinfo("Import finished",
                                f"{added} medicine(s) added, {skipped} skipped.\n"
                                "Skipped rows are listed in the activity log.")
