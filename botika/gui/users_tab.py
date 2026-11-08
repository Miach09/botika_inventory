"""Users page (admin only): add employees, reset passwords, turn accounts on or off."""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from botika import auth
from botika.gui.widgets import Card, add_field, clear_table, guarded, make_table, selected_id

COLUMNS = [("username", "Username", 200, "w"), ("role", "Role", 100, "w"),
           ("status", "Status", 100, "w"), ("created", "Created", 150, "w")]


class UsersTab(ttk.Frame):
    def __init__(self, parent, service, set_status):
        super().__init__(parent)
        self.service, self.set_status = service, set_status
        self.vars = {k: tk.StringVar() for k in ("username", "password", "role")}
        self.vars["role"].set(auth.ROLE_LABELS[auth.ROLE_STAFF])
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        card = Card(self, "Add an Employee Account")
        card.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        form = card.body
        form.columnconfigure(1, weight=1)
        add_field(form, 0, "Username *", ttk.Entry(form, textvariable=self.vars["username"], width=22))
        add_field(form, 1, "Password *", ttk.Entry(form, textvariable=self.vars["password"], show="*"))
        add_field(form, 2, "Role", ttk.Combobox(form, textvariable=self.vars["role"],
                                                state="readonly",
                                                values=list(auth.ROLE_LABELS.values())))
        ttk.Label(form, style="Hint.TLabel", wraplength=240, text=(
            "Staff can receive, issue and adjust stock but cannot delete anything. "
            "Admins can also delete records and manage users.")
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 12))
        ttk.Button(form, text="Add User", style="Success.TButton", command=self.add
                   ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=3, pady=3)

        listing = Card(self, "User accounts", padding=10)
        listing.grid(row=0, column=1, sticky="nsew")
        listing.body.columnconfigure(0, weight=1)
        listing.body.rowconfigure(0, weight=1)
        frame, self.tree = make_table(listing.body, COLUMNS, height=14)
        frame.grid(row=0, column=0, sticky="nsew")
        actions = ttk.Frame(listing.body, style="Card.TFrame")
        actions.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(actions, text="Reset Password", style="Warning.TButton",
                   command=self.reset_password).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Change Role", style="Warning.TButton",
                   command=self.change_role).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Turn Account On / Off", style="Secondary.TButton",
                   command=self.toggle_active).pack(side="left")

    def refresh(self):
        with guarded():
            rows = self.service.list_users()
            clear_table(self.tree)
            for u in rows:
                self.tree.insert("", "end", iid=str(u["id"]), values=(
                    u["username"], auth.ROLE_LABELS[u["role"]],
                    "Active" if u["active"] else "Turned off", u["created_at"]))
            self.set_status(f"{len(rows)} user account(s).")

    def add(self):
        with guarded():
            role = next(k for k, v in auth.ROLE_LABELS.items() if v == self.vars["role"].get())
            self.service.add_user(self.vars["username"].get(), self.vars["password"].get(), role)
            self.vars["username"].set("")
            self.vars["password"].set("")
            self.refresh()
            messagebox.showinfo("User added", "The account was created.")

    def _selected_name(self):
        uid = selected_id(self.tree)
        if uid is None:
            messagebox.showinfo("Select a user", "Click a user in the list first.")
            return None, None
        return uid, self.tree.item(str(uid), "values")[0]

    def reset_password(self):
        uid, name = self._selected_name()
        if uid is None:
            return
        new = simpledialog.askstring("Reset password", f"New password for '{name}':",
                                     show="*", parent=self)
        if new is None:
            return
        with guarded():
            self.service.reset_password(uid, new)
            messagebox.showinfo("Password reset", f"The password for '{name}' was changed.")

    def change_role(self):
        """Switch the selected user between Staff and Admin (fixes a wrong role)."""
        uid, name = self._selected_name()
        if uid is None:
            return
        current = self.tree.item(str(uid), "values")[1]
        new_role = auth.ROLE_STAFF if current == auth.ROLE_LABELS[auth.ROLE_ADMIN] \
            else auth.ROLE_ADMIN
        if not messagebox.askyesno(
                "Change role",
                f"Change '{name}' from {current} to {auth.ROLE_LABELS[new_role]}?\n\n"
                "The change applies right away, even if they are logged in."):
            return
        with guarded():
            self.service.set_user_role(uid, new_role)
            self.refresh()

    def toggle_active(self):
        uid, name = self._selected_name()
        if uid is None:
            return
        turning_off = self.tree.item(str(uid), "values")[2] == "Active"
        verb = "Turn off" if turning_off else "Turn on"
        if not messagebox.askyesno(f"{verb} account", f"{verb} the account '{name}'?"):
            return
        with guarded():
            self.service.set_user_active(uid, not turning_off)
            self.refresh()
