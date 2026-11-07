"""Colours, fonts and ttk styles: a flat dashboard look (dark-blue sidebar,
light content area, white cards, coloured buttons)."""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

PRIMARY = "#4e73df"
PRIMARY_DARK = "#224abe"
SUCCESS = "#1cc88a"
INFO = "#36b9cc"
WARNING = "#f6c23e"
ORANGE = "#fd7e14"
DANGER = "#e74a3b"
SECONDARY = "#858796"
HEAD = "#3a3b45"
TEXT = "#5a5c69"
BG = "#f8f9fc"
CARD = "#ffffff"
BORDER = "#e3e6f0"
FIELD_BORDER = "#d1d3e2"
TABLE_HEAD = "#eaecf4"

_family = "TkDefaultFont"


def font(size=10, bold=False):
    return (_family, size, "bold") if bold else (_family, size)


def blend(color_a: str, color_b: str, t: float) -> str:
    """Mix two #rrggbb colours (t=0 gives a, t=1 gives b)."""
    a = [int(color_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def apply_theme(root: tk.Tk):
    global _family
    families = set(tkfont.families(root))
    for name in ("Segoe UI", "Helvetica Neue", "Noto Sans", "DejaVu Sans"):
        if name in families:
            _family = name
            break
    root.configure(bg=BG)
    root.option_add("*Font", font(10))

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure(".", background=BG, foreground=TEXT, font=font(10),
                    bordercolor=BORDER, focuscolor=BG, troughcolor=TABLE_HEAD)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT)
    style.configure("Hint.TLabel", background=CARD, foreground=SECONDARY, font=font(9))
    style.configure("Title.TLabel", background=BG, foreground=HEAD, font=font(18, True))

    for entry in ("TEntry", "TCombobox"):
        style.configure(entry, fieldbackground="white", background="white",
                        bordercolor=FIELD_BORDER, lightcolor=FIELD_BORDER,
                        darkcolor=FIELD_BORDER, padding=5, foreground=HEAD)
    style.map("TEntry", bordercolor=[("focus", PRIMARY)], lightcolor=[("focus", PRIMARY)],
              darkcolor=[("focus", PRIMARY)])
    style.map("TCombobox", bordercolor=[("focus", PRIMARY)],
              fieldbackground=[("readonly", "white")],
              foreground=[("readonly", HEAD)])
    style.configure("TCombobox", arrowcolor=SECONDARY)

    buttons = {"Primary": (PRIMARY, "#2e59d9", "white"),
               "Success": (SUCCESS, "#17a673", "white"),
               "Warning": (WARNING, "#f4b619", HEAD),
               "Danger": (DANGER, "#e02d1b", "white"),
               "Secondary": (SECONDARY, "#6b6d7d", "white")}
    for name, (color, hover, fg) in buttons.items():
        style.configure(f"{name}.TButton", background=color, foreground=fg,
                        bordercolor=color, lightcolor=color, darkcolor=color,
                        focusthickness=0, padding=(14, 7), font=font(10, True), relief="flat")
        style.map(f"{name}.TButton",
                  background=[("disabled", FIELD_BORDER), ("pressed", hover), ("active", hover)],
                  bordercolor=[("pressed", hover), ("active", hover)],
                  foreground=[("disabled", "white")])

    style.configure("Treeview", background="white", fieldbackground="white",
                    foreground=TEXT, rowheight=28, bordercolor=BORDER, borderwidth=0,
                    font=font(10))
    style.configure("Treeview.Heading", background=TABLE_HEAD, foreground=HEAD,
                    font=font(10, True), relief="flat", padding=(6, 7), borderwidth=0)
    style.map("Treeview.Heading", background=[("active", "#dfe3f0")])
    style.map("Treeview", background=[("selected", PRIMARY)],
              foreground=[("selected", "white")])

    # Work around a Tk bug where row tag colours are ignored on some versions.
    def fixed_map(option):
        return [e for e in style.map("Treeview", query_opt=option)
                if e[:2] != ("!disabled", "!selected")]
    style.map("Treeview", foreground=fixed_map("foreground"),
              background=fixed_map("background"))
    style.configure("Vertical.TScrollbar", background=TABLE_HEAD, troughcolor=BG,
                    bordercolor=BG, arrowcolor=SECONDARY)
    style.configure("Horizontal.TScrollbar", background=TABLE_HEAD, troughcolor=BG,
                    bordercolor=BG, arrowcolor=SECONDARY)
