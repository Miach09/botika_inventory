"""Reports page: CSV export and import (file management)."""
from datetime import date
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from botika import config
from botika.gui import theme
from botika.gui.widgets import Card, guarded


class ReportsTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent)
        self.service, self.set_status = service, set_status
        self.days_var = tk.StringVar(value="90")
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        export = Card(self, "Export to CSV")
        export.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 14))
        for text, cmd in [("Medicines and stock levels", self.export_medicines),
                          ("All stock batches", self.export_batches),
                          ("Stock movement history", self.export_movements)]:
            ttk.Button(export.body, text=text, style="Primary.TButton", command=cmd).pack(
                fill="x", pady=3)
        row = ttk.Frame(export.body, style="Card.TFrame")
        row.pack(fill="x", pady=(10, 0))
        ttk.Label(row, text="Expiry report within", style="Card.TLabel").pack(side="left")
        ttk.Combobox(row, textvariable=self.days_var, width=5, state="readonly",
                     values=[str(d) for d in config.EXPIRY_WINDOWS]).pack(side="left", padx=6)
        ttk.Label(row, text="days", style="Card.TLabel").pack(side="left")
        ttk.Button(row, text="Export", style="Warning.TButton",
                   command=self.export_expiry).pack(side="right")

        importer = Card(self, "Import medicines from CSV")
        importer.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 14))
        ttk.Label(importer.body, style="Hint.TLabel", justify="left", text=(
            "Required columns: brand_name, generic_name.\n"
            "Optional: strength, dosage_form, category, reorder_level, unit_cost.\n"
            "Rows with problems are skipped and listed in the activity log.")
        ).pack(anchor="w", pady=(0, 10))
        ttk.Button(importer.body, text="Save blank template...", style="Secondary.TButton",
                   command=self.save_template).pack(fill="x", pady=3)
        ttk.Button(importer.body, text="Import CSV file...", style="Success.TButton",
                   command=self.import_csv).pack(fill="x", pady=3)

        log_card = Card(self, "Activity", padding=10)
        log_card.grid(row=1, column=0, columnspan=2, sticky="nsew")
        log_card.body.columnconfigure(0, weight=1)
        log_card.body.rowconfigure(0, weight=1)
        self.log = tk.Text(log_card.body, height=10, state="disabled", wrap="word",
                           relief="flat", bg=theme.BG, fg=theme.TEXT, padx=10, pady=8,
                           font=theme.font(10), highlightthickness=1,
                           highlightbackground=theme.BORDER)
        self.log.grid(row=0, column=0, sticky="nsew")

    def refresh(self):
        self.set_status("Ready.")  # nothing to reload on this page

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
