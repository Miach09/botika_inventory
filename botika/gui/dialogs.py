"""Pop-up windows used by the Stock page. Both open in the middle of the screen."""
import tkinter as tk
from tkinter import ttk

from botika import config
from botika.gui import theme
from botika.gui.widgets import (Card, add_field, center_window, clear_table, guarded,
                                make_table)


class MovementDialog(tk.Toplevel):
    """Issue, dispose or adjust the quantity of one batch."""

    def __init__(self, parent, service, batch):
        super().__init__(parent)
        self.withdraw()                      # build first, show once it is centred
        self.service, self.batch = service, batch
        self.changed = False
        self.title("Issue / Adjust Stock")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.configure(bg=theme.CARD)

        body = ttk.Frame(self, padding=18, style="Card.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        name = f"{batch['brand_name']} {batch['strength']}".strip()
        ttk.Label(body, text=f"{name}  |  Batch {batch['batch_number']}",
                  style="Card.TLabel", font=theme.font(11, True)).grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(body, text=f"Current quantity: {batch['quantity']}",
                  style="Card.TLabel").grid(row=1, column=0, columnspan=2,
                                            sticky="w", pady=(0, 10))

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
                  style="Hint.TLabel").grid(row=5, column=0, columnspan=2, sticky="w")

        buttons = ttk.Frame(body, style="Card.TFrame")
        buttons.grid(row=6, column=0, columnspan=2, pady=(14, 0), sticky="e")
        ttk.Button(buttons, text="Save", style="Success.TButton",
                   command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", style="Secondary.TButton",
                   command=self.destroy).pack(side="left")

        center_window(self)
        self.deiconify()
        self.grab_set()

    def save(self):
        with guarded():
            raw = {"movement_type": self.labels.get(self.type_var.get()),
                   "quantity": self.qty_var.get(), "reason": self.reason_var.get()}
            self.service.record_movement(self.batch["id"], raw)
            self.changed = True
            self.destroy()


class HistoryDialog(tk.Toplevel):
    """Read-only list of every stock movement for one batch.

    Long reasons are shortened in the table; click a row to read the full text
    in the panel below. The Close button is packed first so it is never hidden.
    """

    WIDTH, HEIGHT = 880, 540

    def __init__(self, parent, service, batch):
        super().__init__(parent)
        self.withdraw()
        self.title("Batch History")
        self.minsize(720, 440)
        self.transient(parent.winfo_toplevel())
        self.configure(bg=theme.BG)
        self.details = {}

        name = f"{batch['brand_name']} {batch['strength']}".strip()
        ttk.Label(self, text=f"{name}  |  Batch {batch['batch_number']}",
                  font=theme.font(11, True), foreground=theme.HEAD).pack(
            side="top", anchor="w", padx=14, pady=(12, 6))

        # bottom widgets first, so they always keep their space when the window is small
        self.close_button = ttk.Button(self, text="Close", style="Secondary.TButton",
                                       command=self.destroy)
        self.close_button.pack(side="bottom", pady=(6, 14))
        card = Card(self, "Full details of the selected movement", padding=8)
        card.pack(side="bottom", fill="x", padx=14, pady=(8, 0))
        self.detail_text = tk.Text(card.body, height=4, wrap="word", state="disabled",
                                   relief="flat", bg=theme.BG, fg=theme.TEXT,
                                   padx=8, pady=6, font=theme.font(10),
                                   highlightthickness=1, highlightbackground=theme.BORDER)
        self.detail_text.pack(fill="x")

        frame, self.tree = make_table(self, [
            ("when", "Date / time", 140, "w"), ("type", "Movement", 110, "w"),
            ("qty", "Qty", 60, "e"), ("by", "Done by", 110, "w"),
            ("reason", "Reason", 370, "w")], height=10)
        frame.pack(side="top", fill="both", expand=True, padx=14)
        self.tree.bind("<<TreeviewSelect>>", self._show_detail)

        with guarded():
            clear_table(self.tree)
            for m in service.list_movements(batch["id"]):
                iid = str(m["id"])
                self.details[iid] = (f"{m['moved_at']}   |   {m['movement_type']}   |   "
                                     f"Quantity: {m['quantity']}   |   "
                                     f"Done by: {m['performed_by'] or '(not recorded)'}\n"
                                     f"{m['reason'] or '(no reason recorded)'}")
                self.tree.insert("", "end", iid=iid, values=(
                    m["moved_at"], m["movement_type"], m["quantity"],
                    m["performed_by"], m["reason"]))
        self._set_detail("Click a row above to read its full reason here.")

        center_window(self, self.WIDTH, self.HEIGHT)
        self.deiconify()

    def _set_detail(self, text):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def _show_detail(self, _event=None):
        selection = self.tree.selection()
        if selection:
            self._set_detail(self.details.get(selection[0], ""))
