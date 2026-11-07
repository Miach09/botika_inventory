"""Out of Stock page: medicines that are sold out or at/below their reorder level."""
from tkinter import ttk

from botika.gui.widgets import Card, clear_table, guarded, make_table

COLUMNS = [("status", "Status", 80, "center"), ("brand", "Brand", 130, "w"),
           ("generic", "Generic", 120, "w"), ("strength", "Strength", 85, "w"),
           ("category", "Category", 125, "w"), ("stock", "Usable", 70, "e"),
           ("reorder", "Reorder", 80, "e"), ("expired", "Expired", 80, "e"),
           ("supplier", "Last supplier", 170, "w")]


class OutOfStockTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent)
        self.service, self.set_status = service, set_status
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        card = Card(self, "Medicines to reorder", padding=10)
        card.grid(row=0, column=0, sticky="nsew")
        ttk.Label(card.body, style="Hint.TLabel", text=(
            "OUT = no usable stock. LOW = at or below the reorder level. "
            "Expired units are not counted as usable.")).pack(anchor="w", pady=(0, 8))
        frame, self.tree = make_table(card.body, COLUMNS, height=16)
        frame.pack(fill="both", expand=True)

    def refresh(self):
        with guarded():
            rows = self.service.stock_alerts()
            clear_table(self.tree)
            for m in rows:
                self.tree.insert("", "end", iid=str(m["id"]), tags=(m["stock_status"],),
                                 values=(m["stock_status"], m["brand_name"], m["generic_name"],
                                         m["strength"], m["category"] or "", m["usable_stock"],
                                         m["reorder_level"], m["expired_stock"],
                                         m["last_supplier"]))
            self.set_status(f"{len(rows)} medicine(s) need attention.")
