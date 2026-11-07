"""Dashboard: key numbers and a list of items that need attention."""
import tkinter as tk
from tkinter import ttk

from botika.gui.widgets import clear_table, guarded, make_table

CARDS = [("medicines", "Medicines"), ("units", "Usable units"),
         ("low_stock", "Low / out of stock"), ("expiring_30", "Expiring in 30 days"),
         ("expired", "Expired batches"), ("value", "Stock value (PHP)")]
ALERT_TAGS = {"Expired": "EXPIRED", "Expiring soon": "EXPIRING_30",
              "Out of stock": "OUT", "Low stock": "LOW"}


class DashboardTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent, padding=10)
        self.service, self.set_status = service, set_status
        self.vars = {key: tk.StringVar(value="-") for key, _ in CARDS}

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Inventory Overview",
                  font=("TkDefaultFont", 14, "bold")).pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        cards = ttk.Frame(self)
        cards.pack(fill="x", pady=10)
        for i, (key, title) in enumerate(CARDS):
            cards.columnconfigure(i, weight=1, uniform="card")
            box = ttk.LabelFrame(cards, text=title, padding=8)
            box.grid(row=0, column=i, sticky="ew", padx=4)
            ttk.Label(box, textvariable=self.vars[key],
                      font=("TkDefaultFont", 18, "bold")).pack()

        ttk.Label(self, text="Items that need attention",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(6, 4))
        frame, self.tree = make_table(self, [
            ("kind", "Alert", 120, "w"), ("item", "Medicine", 240, "w"),
            ("detail", "Details", 520, "w")], height=14)
        frame.pack(fill="both", expand=True)

    def refresh(self):
        with guarded():
            summary = self.service.dashboard_summary()
            for key, _ in CARDS:
                value = summary[key]
                self.vars[key].set(f"{value:,.2f}" if key == "value" else f"{value:,}")
            clear_table(self.tree)
            for i, (kind, item, detail) in enumerate(self.service.alerts()):
                self.tree.insert("", "end", iid=str(i), values=(kind, item, detail),
                                 tags=(ALERT_TAGS.get(kind, ""),))
            self.set_status("Dashboard updated.")
