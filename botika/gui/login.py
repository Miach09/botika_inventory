"""Login window (shown before the main window) and the change-password dialog."""
import tkinter as tk
from tkinter import ttk

from botika import auth, config
from botika.auth import AuthError
from botika.gui import theme
from botika.gui.widgets import Card, add_field, center_window


class LoginWindow(tk.Tk):
    """Log in, or create the first admin account when no account exists yet."""

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.success = False
        self.setup_mode = not service.has_users()
        self.title(config.APP_TITLE)
        self.resizable(False, False)
        self.configure(bg=theme.BG)
        theme.apply_theme(self)

        tk.Label(self, text="Botika Inventory", bg=theme.BG, fg=theme.HEAD,
                 font=theme.font(18, True)).pack(padx=40, pady=(26, 2))
        subtitle = ("Create the admin account to get started" if self.setup_mode
                    else "Log in to continue")
        tk.Label(self, text=subtitle, bg=theme.BG, fg=theme.SECONDARY,
                 font=theme.font(10)).pack(pady=(0, 14))

        card = Card(self, "Create admin account" if self.setup_mode else "Log in")
        card.pack(padx=30, fill="x")
        form = card.body
        form.columnconfigure(1, weight=1)
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.confirm = tk.StringVar()
        first = add_field(form, 0, "Username", ttk.Entry(form, textvariable=self.username, width=26))
        add_field(form, 1, "Password", ttk.Entry(form, textvariable=self.password, show="*"))
        if self.setup_mode:
            add_field(form, 2, "Confirm password",
                      ttk.Entry(form, textvariable=self.confirm, show="*"))
            ttk.Label(form, style="Hint.TLabel", wraplength=300, text=(
                "This first account is the admin. Only an admin can delete records "
                "and manage other users. Use at least "
                f"{auth.MIN_PASSWORD_LENGTH} characters.")
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.error = tk.StringVar()
        tk.Label(self, textvariable=self.error, bg=theme.BG, fg=theme.DANGER,
                 font=theme.font(9), wraplength=320).pack(pady=(8, 0))
        self.submit_button = ttk.Button(
            self, text="Create admin account" if self.setup_mode else "Log in",
            style="Success.TButton", command=self.submit)
        self.submit_button.pack(pady=(8, 24), ipadx=14)

        self.bind("<Return>", lambda _e: self.submit())
        center_window(self)
        first.focus_set()

    def submit(self):
        try:
            if self.setup_mode:
                if self.password.get() != self.confirm.get():
                    raise AuthError("The two passwords do not match.")
                self.service.create_first_admin(self.username.get(), self.password.get())
            self.service.login(self.username.get(), self.password.get())
        except AuthError as exc:
            self.error.set(str(exc))
            self.password.set("")
            self.confirm.set("")
            return
        self.success = True
        self.destroy()


def run_login(service) -> bool:
    """Show the login window. Returns True once someone is logged in."""
    window = LoginWindow(service)
    window.mainloop()
    return window.success


class ChangePasswordDialog(tk.Toplevel):
    def __init__(self, parent, service):
        super().__init__(parent)
        self.service = service
        self.withdraw()
        self.title("Change password")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.configure(bg=theme.BG)
        card = Card(self, "Change your password")
        card.pack(padx=16, pady=(16, 6))
        form = card.body
        form.columnconfigure(1, weight=1)
        self.old, self.new, self.confirm = tk.StringVar(), tk.StringVar(), tk.StringVar()
        first = add_field(form, 0, "Current password",
                          ttk.Entry(form, textvariable=self.old, show="*", width=24))
        add_field(form, 1, "New password", ttk.Entry(form, textvariable=self.new, show="*"))
        add_field(form, 2, "Confirm new password",
                  ttk.Entry(form, textvariable=self.confirm, show="*"))
        self.error = tk.StringVar()
        tk.Label(self, textvariable=self.error, bg=theme.BG, fg=theme.DANGER,
                 font=theme.font(9), wraplength=300).pack()
        row = tk.Frame(self, bg=theme.BG)
        row.pack(pady=(4, 14))
        self.save_button = ttk.Button(row, text="Save", style="Success.TButton",
                                      command=self.save)
        self.save_button.pack(side="left", padx=4)
        ttk.Button(row, text="Cancel", style="Secondary.TButton",
                   command=self.destroy).pack(side="left", padx=4)
        self.bind("<Return>", lambda _e: self.save())
        center_window(self)
        self.deiconify()
        first.focus_set()
        self.grab_set()

    def save(self):
        try:
            if self.new.get() != self.confirm.get():
                raise AuthError("The two new passwords do not match.")
            self.service.change_own_password(self.old.get(), self.new.get())
        except AuthError as exc:
            self.error.set(str(exc))
            return
        self.destroy()
        from tkinter import messagebox
        messagebox.showinfo("Password changed", "Your password was changed.")
