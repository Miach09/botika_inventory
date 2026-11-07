"""Pop-up windows used by the Stock tab."""
import tkinter as tk
from tkinter import ttk

from botika import config
from botika.gui.widgets import add_field, clear_table, guarded, make_table


class MovementDialog(tk.Toplevel):
    """Issue, dispose or adjust the quantity of one batch."""

    def __init__(self, parent, service, batch):
        super().__init__(parent)
        self.service, self.batch = service, batch
        self.changed = False
        self.title("Issue / Adjust Stock")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        name = f"{batch['brand_name']} {batch['strength']}".strip()
        ttk.Label(body, text=f"{name}  |  Batch {batch['batch_number']}",
                  font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0,
                                                           columnspan=2, sticky="w")
        ttk.Label(body, text=f"Current quantity: {batch['quantity']}").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.type_var = tk.StringVar()
        self.qty_var = tk.StringVar()
        self.reason_var = tk.StringVar()
        self.labels = {label: key for key, label in config.MOVEMENT_LABELS.items()}
        combo = ttk.Combobox(body, textvariable=self.type_var, state="readonly",
                             values=list(self.labels), width=34)
        combo.current(0)
        add_field(body, 2, "Movement type", combo)
        add_field(body, 3, "Quantity *", ttk.Entry(body, textvariable=self.qty_var))
        add_field(body, 4, "Reason", ttk.Entry(body, textvariable=self.reason_var))
        ttk.Label(body, text="Reason is required for disposal and count adjustments.",
                  foreground="#666").grid(row=5, column=0, columnspan=2, sticky="w")

        buttons = ttk.Frame(body)
        buttons.grid(row=6, column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(buttons, text="Save", command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left")
        self.grab_set()

    def save(self):
        with guarded():
            raw = {"movement_type": self.labels.get(self.type_var.get()),
                   "quantity": self.qty_var.get(), "reason": self.reason_var.get()}
            self.service.record_movement(self.batch["id"], raw)
            self.changed = True
            self.destroy()


class HistoryDialog(tk.Toplevel):
    """Read-only list of every stock movement for one batch."""

    def __init__(self, parent, service, batch):
        super().__init__(parent)
        self.title("Batch History")
        self.geometry("720x360")
        self.transient(parent.winfo_toplevel())
        name = f"{batch['brand_name']} {batch['strength']}".strip()
        ttk.Label(self, text=f"{name}  |  Batch {batch['batch_number']}",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        frame, tree = make_table(self, [
            ("when", "Date / time", 130, "w"), ("type", "Movement", 100, "w"),
            ("qty", "Qty", 60, "e"), ("reason", "Reason", 360, "w")])
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        with guarded():
            clear_table(tree)
            for m in service.list_movements(batch["id"]):
                tree.insert("", "end", iid=str(m["id"]), values=(
                    m["moved_at"], m["movement_type"], m["quantity"], m["reason"]))
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=(0, 10))
