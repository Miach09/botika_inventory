"""Small reusable GUI helpers shared by all tabs."""
import logging
import queue
import threading
import tkinter as tk
from contextlib import contextmanager
from tkinter import messagebox, ttk

from botika.api_client import ApiError
from botika.gui import theme
from botika.database import DatabaseError
from botika.reports import ReportError
from botika.validators import ValidationError

log = logging.getLogger(__name__)

# Row colours used for stock / expiry status
TAG_COLORS = {
    "EXPIRED": "#fbdcd9",
    "EXPIRING_30": "#fde5d0",
    "EXPIRING_60": "#fff3cd",
    "EXPIRING_90": "#dcebf9",
    "DEPLETED": "#eceef3",
    "OUT": "#fbdcd9",
    "LOW": "#fde5d0",
}


def make_table(parent, columns, height=10):
    """Create a Treeview with scrollbars. columns = [(key, heading, width, anchor)]."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height, selectmode="browse")
    for key, heading, width, anchor in columns:
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor=anchor, stretch=True)
    ysb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    ysb.grid(row=0, column=1, sticky="ns")
    xsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    for tag, color in TAG_COLORS.items():
        tree.tag_configure(tag, background=color)
    return frame, tree


def center_window(win, width=None, height=None):
    """Size a window (or use its natural size) and put it in the middle of the screen."""
    win.update_idletasks()
    w = width or win.winfo_reqwidth()
    h = height or win.winfo_reqheight()
    x = max((win.winfo_screenwidth() - w) // 2, 0)
    y = max((win.winfo_screenheight() - h) // 2, 0)
    win.geometry(f"{w}x{h}+{x}+{y}")


def maximize_window(win):
    """Open maximized on Windows, Linux and macOS (each needs a different call)."""
    try:
        win.state("zoomed")                      # Windows (and some Linux builds)
    except tk.TclError:
        try:
            win.attributes("-zoomed", True)      # most Linux window managers
        except tk.TclError:                      # macOS: fill the screen instead
            win.geometry(f"{win.winfo_screenwidth()}x{win.winfo_screenheight()}+0+0")


def clear_table(tree):
    tree.delete(*tree.get_children())


def selected_id(tree):
    """Return the selected row's record id (stored as the row iid) or None."""
    selection = tree.selection()
    return int(selection[0]) if selection else None


@contextmanager
def guarded():
    """Show a friendly message for any expected error instead of crashing."""
    try:
        yield
    except ValidationError as exc:
        messagebox.showwarning("Please check your input",
                               "\n".join(f"\u2022 {e}" for e in exc.errors))
    except DatabaseError as exc:
        messagebox.showerror("Database error", str(exc))
    except ReportError as exc:
        messagebox.showerror("File error", str(exc))
    except ApiError as exc:
        messagebox.showwarning("Drug information unavailable", str(exc))
    except Exception as exc:  # last resort: log it and keep the app running
        log.exception("Unexpected error")
        messagebox.showerror("Unexpected error",
                             f"Something went wrong: {exc}\nDetails were saved to the log file.")


def run_async(widget, func, on_success, on_error):
    """Run `func` in a background thread; callbacks run on the Tk main thread.

    Used for the REST API call so the window never freezes while waiting.
    """
    results = queue.Queue()

    def worker():
        try:
            results.put(("ok", func()))
        except Exception as exc:  # delivered to on_error on the main thread
            results.put(("error", exc))

    def poll():
        try:
            kind, payload = results.get_nowait()
        except queue.Empty:
            widget.after(100, poll)
            return
        (on_success if kind == "ok" else on_error)(payload)

    threading.Thread(target=worker, daemon=True).start()
    widget.after(100, poll)


def add_field(parent, row, label, widget):
    """One 'label + input' row inside a card."""
    ttk.Label(parent, text=label, style="Card.TLabel").grid(
        row=row, column=0, sticky="w", pady=4, padx=(0, 10))
    widget.grid(row=row, column=1, sticky="ew", pady=4)
    return widget


class Card(tk.Frame):
    """White panel with a thin border and an optional blue title bar.

    Put your widgets in `card.body`.
    """

    def __init__(self, parent, title=None, padding=14):
        super().__init__(parent, bg=theme.BORDER)
        inner = tk.Frame(self, bg=theme.CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        if title:
            head = tk.Frame(inner, bg=theme.BG)
            head.pack(fill="x")
            tk.Label(head, text=title, bg=theme.BG, fg=theme.PRIMARY,
                     font=theme.font(11, True), anchor="w").pack(side="left", padx=14, pady=10)
            tk.Frame(inner, bg=theme.BORDER, height=1).pack(fill="x")
        self.body = ttk.Frame(inner, style="Card.TFrame", padding=padding)
        self.body.pack(fill="both", expand=True)


class StatCard(tk.Frame):
    """Number card with a coloured left edge, used on the dashboard."""

    def __init__(self, parent, title, accent, variable):
        super().__init__(parent, bg=theme.BORDER)
        inner = tk.Frame(self, bg=theme.CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(inner, bg=accent, width=5).pack(side="left", fill="y")
        body = tk.Frame(inner, bg=theme.CARD)
        body.pack(side="left", fill="both", expand=True, padx=16, pady=14)
        tk.Label(body, text=title.upper(), bg=theme.CARD, fg=accent,
                 font=theme.font(9, True), anchor="w").pack(anchor="w")
        tk.Label(body, textvariable=variable, bg=theme.CARD, fg=theme.HEAD,
                 font=theme.font(22, True), anchor="w").pack(anchor="w", pady=(4, 0))
