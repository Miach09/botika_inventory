"""Main window: notebook navigation, status bar and menu."""
import tkinter as tk
from tkinter import messagebox, ttk

from botika import config
from botika.gui.dashboard_tab import DashboardTab
from botika.gui.medicines_tab import MedicinesTab
from botika.gui.reports_tab import ReportsTab
from botika.gui.stock_tab import StockTab
from botika.gui.suppliers_tab import SuppliersTab


class BotikaApp(tk.Tk):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.title(config.APP_TITLE)
        self.geometry("1180x720")
        self.minsize(1020, 640)
        self._apply_style()
        self._build_menu()

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=(8, 2)).pack(fill="x", side="bottom", pady=(6, 0))
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self.tabs = []
        for title, cls in (("Dashboard", DashboardTab), ("Medicines", MedicinesTab),
                           ("Stock Batches", StockTab), ("Suppliers", SuppliersTab),
                           ("Reports", ReportsTab)):
            tab = cls(self.notebook, self.service, self.set_status)
            self.notebook.add(tab, text=f"   {title}   ")
            self.tabs.append(tab)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._on_tab_changed()

    def set_status(self, message):
        self.status_var.set(message)

    def _on_tab_changed(self, _event=None):
        self.tabs[self.notebook.index("current")].refresh()

    def _apply_style(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TNotebook.Tab", padding=(10, 6))
        style.configure("Treeview", rowheight=24)
        style.configure("Treeview.Heading", font=("TkDefaultFont", 9, "bold"))

        # Work around a Tk bug where row tag colours are ignored on some versions.
        def fixed_map(option):
            return [e for e in style.map("Treeview", query_opt=option)
                    if e[:2] != ("!disabled", "!selected")]
        style.map("Treeview", foreground=fixed_map("foreground"),
                  background=fixed_map("background"))

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
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
