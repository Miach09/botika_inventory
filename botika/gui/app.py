"""Main window: sidebar navigation, top bar, page area and status bar."""
from datetime import datetime
import time
import tkinter as tk
from tkinter import messagebox, ttk

from botika import config
from botika.gui import theme
from botika.gui.dashboard_tab import DashboardTab
from botika.gui.login import ChangePasswordDialog
from botika.gui.medicines_tab import MedicinesTab
from botika.gui.out_of_stock_tab import OutOfStockTab
from botika.gui.reports_tab import ReportsTab
from botika.gui.sidebar import Sidebar
from botika.gui.stock_tab import StockTab
from botika.gui.suppliers_tab import SuppliersTab
from botika.gui.users_tab import UsersTab
from botika.gui.widgets import maximize_window

# (menu label, icon, page title, page class)
PAGES = [
    ("Dashboard", "dashboard", "Dashboard", DashboardTab),
    ("Medicines", "medicines", "Manage Medicines", MedicinesTab),
    ("Stock Batches", "batches", "Stock Batches", StockTab),
    ("Out of Stock", "outofstock", "Out of Stock and Low Stock", OutOfStockTab),
    ("Suppliers", "suppliers", "Suppliers", SuppliersTab),
    ("Reports", "reports", "Reports and Files", ReportsTab),
]
# Only shown to admins
USERS_PAGE = ("Users", "suppliers", "Manage Users", UsersTab)


class BotikaApp(tk.Tk):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.logged_out = False
        self._last_activity = time.monotonic()
        self.pages = PAGES + ([USERS_PAGE] if service.is_admin else [])
        self.title(config.APP_TITLE)
        # Normal (restored) size: fits small screens such as 1366x768, centred.
        width = min(1320, self.winfo_screenwidth() - 40)
        height = min(780, self.winfo_screenheight() - 110)
        self.geometry(f"{width}x{height}+{(self.winfo_screenwidth() - width) // 2}+20")
        self.minsize(1000, 620)
        theme.apply_theme(self)
        self._build_menu()

        self.status_var = tk.StringVar(value="Ready")
        self.title_var = tk.StringVar()

        self.sidebar = Sidebar(self, "Botika Inventory",
                               [(label, icon) for label, icon, _t, _c in self.pages], self.show)
        self.sidebar.pack(side="left", fill="y")

        right = tk.Frame(self, bg=theme.BG)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, textvariable=self.status_var, anchor="w", bg=theme.CARD,
                 fg=theme.SECONDARY, font=theme.font(9), padx=16, pady=5
                 ).pack(side="bottom", fill="x")
        tk.Frame(right, bg=theme.BORDER, height=1).pack(side="bottom", fill="x")

        topbar = tk.Frame(right, bg=theme.CARD, height=60)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        tk.Label(topbar, textvariable=self.title_var, bg=theme.CARD, fg=theme.HEAD,
                 font=theme.font(16, True)).pack(side="left", padx=24)
        self.clock_var = tk.StringVar()
        tk.Label(topbar, textvariable=self.clock_var, bg=theme.CARD,
                 fg=theme.SECONDARY, font=theme.font(10)).pack(side="right", padx=(12, 24))
        ttk.Button(topbar, text="Log out", style="Secondary.TButton",
                   command=self.logout).pack(side="right", padx=4)
        ttk.Button(topbar, text="Change password", style="Secondary.TButton",
                   command=lambda: ChangePasswordDialog(self, self.service)
                   ).pack(side="right", padx=4)
        role = "Admin" if service.is_admin else "Staff"
        tk.Label(topbar, text=f"{service.username} ({role})", bg=theme.CARD,
                 fg=theme.HEAD, font=theme.font(10, True)).pack(side="right", padx=(12, 8))
        self._clock_job = None
        self._tick()
        tk.Frame(right, bg=theme.BORDER, height=1).pack(fill="x")

        area = ttk.Frame(right, padding=(22, 18))
        area.pack(fill="both", expand=True)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        self.tabs = []
        for _label, _icon, _title, cls in self.pages:
            page = cls(area, self.service, self.set_status)
            page.grid(row=0, column=0, sticky="nsew")
            self.tabs.append(page)
        for event in ("<Key>", "<Button>", "<Motion>"):      # any use counts as activity
            self.bind_all(event, self._touch, add="+")
        self.show(0)
        maximize_window(self)      # start full screen; the normal size is used if restored

    def set_status(self, message):
        self.status_var.set(message)

    def _tick(self):
        """Show today's date and the current time, refreshed every second."""
        if time.monotonic() - self._last_activity > config.IDLE_LOGOUT_MINUTES * 60:
            self.logout()                       # nobody has used the app for a while
            return
        now = datetime.now()
        time_text = now.strftime("%I:%M:%S %p").lstrip("0")      # 3:05:09 PM
        self.clock_var.set(f"{now.strftime('%A, %B %d, %Y')}   |   {time_text}")
        self._clock_job = self.after(1000, self._tick)

    def _touch(self, _event=None):
        self._last_activity = time.monotonic()

    def logout(self):
        """Close the main window; main.py then shows the login window again."""
        self.logged_out = True
        self.service.logout()
        self.destroy()

    def destroy(self):
        if self._clock_job is not None:
            self.after_cancel(self._clock_job)
            self._clock_job = None
        super().destroy()

    def show(self, index):
        """Bring one page to the front and refresh its data."""
        self.current = index
        self.tabs[index].tkraise()
        self.sidebar.set_active(index)
        self.title_var.set(self.pages[index][2])
        self.tabs[index].refresh()

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Log out", command=self.logout)
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menubar)

    def _about(self):
        messagebox.showinfo(
            "About",
            f"{config.APP_TITLE}\n\nTracks medicine stock, batches and expiry dates.\n"
            "Drug information comes from the openFDA API and is for reference only,\n"
            "not medical advice.")
