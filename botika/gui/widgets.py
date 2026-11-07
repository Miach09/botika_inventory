"""Small reusable GUI helpers shared by all tabs."""
import logging
import queue
import threading
import tkinter as tk
from contextlib import contextmanager
from tkinter import messagebox, ttk

from botika.api_client import ApiError
from botika.database import DatabaseError
from botika.reports import ReportError
from botika.validators import ValidationError

log = logging.getLogger(__name__)

# Row colours used for stock / expiry status
TAG_COLORS = {
    "EXPIRED": "#f8d7da",
    "EXPIRING_30": "#ffe0b3",
    "EXPIRING_60": "#fff3cd",
    "EXPIRING_90": "#e3f2fd",
    "DEPLETED": "#e9ecef",
    "OUT": "#f8d7da",
    "LOW": "#ffe0b3",
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
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
    widget.grid(row=row, column=1, sticky="ew", pady=3)
    return widget
