"""Dashboard: key numbers and a list of items that need attention."""
import tkinter as tk
from tkinter import ttk

from botika.gui import theme
from botika.gui.widgets import Card, StatCard, clear_table, guarded, make_table

# key, title, accent colour
CARDS = [("medicines", "Medicines", theme.PRIMARY),
         ("units", "Usable units", theme.SUCCESS),
         ("value", "Stock value (PHP)", theme.INFO),
         ("low_stock", "Low / out of stock", theme.WARNING),
         ("expiring_30", "Expiring in 30 days", theme.ORANGE),
         ("expired", "Expired batches", theme.DANGER)]
ALERT_TAGS = {"Expired": "EXPIRED", "Expiring soon": "EXPIRING_30",
              "Out of stock": "OUT", "Low stock": "LOW"}


class DashboardTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent)
        self.service, self.set_status = service, set_status
        self.vars = {key: tk.StringVar(value="-") for key, _t, _c in CARDS}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        cards = ttk.Frame(self)
        cards.grid(row=0, column=0, sticky="ew")
        for i, (key, title, accent) in enumerate(CARDS):
            cards.columnconfigure(i % 3, weight=1, uniform="stat")
            StatCard(cards, title, accent, self.vars[key]).grid(
                row=i // 3, column=i % 3, sticky="ew",
                padx=(0 if i % 3 == 0 else 8, 0 if i % 3 == 2 else 8),
                pady=(0, 14))

        card = Card(self, "Items that need attention", padding=10)
        card.grid(row=1, column=0, sticky="nsew")
        frame, self.tree = make_table(card.body, [
            ("kind", "Alert", 130, "w"), ("item", "Medicine", 260, "w"),
            ("detail", "Details", 560, "w")], height=12)
        frame.pack(fill="both", expand=True)

    def refresh(self):
        with guarded():
            summary = self.service.dashboard_summary()
            for key, _t, _c in CARDS:
                value = summary[key]
                self.vars[key].set(f"{value:,.2f}" if key == "value" else f"{value:,}")
            clear_table(self.tree)
            for i, (kind, item, detail) in enumerate(self.service.alerts()):
                self.tree.insert("", "end", iid=str(i), values=(kind, item, detail),
                                 tags=(ALERT_TAGS.get(kind, ""),))
            self.set_status("Dashboard updated.")
