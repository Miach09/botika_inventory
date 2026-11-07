"""Left navigation bar drawn on a canvas so it can have a gradient background.

The menu items are created once per resize and only *recoloured* on hover or
click. (Deleting and recreating the item under the mouse makes Tk send new
Enter/Leave events, which would redraw again and freeze the window.)
"""
import tkinter as tk

from botika.gui import theme
from botika.gui.icons import ICONS

WIDTH = 230
ROW = 46


class Sidebar(tk.Canvas):
    def __init__(self, parent, brand, items, on_select):
        """items = [(label, icon_key), ...]; on_select(index) is called on click."""
        super().__init__(parent, width=WIDTH, highlightthickness=0, bd=0,
                         bg=theme.PRIMARY_DARK)
        self.brand, self.items, self.on_select = brand, items, on_select
        self.active, self.hover = 0, None
        self.icons = {key: tk.PhotoImage(data=ICONS[key]) for _, key in items}
        self._rects, self._texts = [], []
        self._size = (0, 0)
        self.bind("<Configure>", self._on_configure)

    def set_active(self, index):
        self.active = index
        self._paint()

    # ---- drawing -----------------------------------------------------
    def _color_at(self, y):
        height = max(self.winfo_height(), 1)
        return theme.blend(theme.PRIMARY, theme.PRIMARY_DARK, min(y / height, 1))

    def _on_configure(self, event):
        size = (event.width, event.height)
        if size == self._size:          # ignore events that did not change the size
            return
        self._size = size
        self._build()

    def _build(self):
        self.delete("all")
        height = max(self.winfo_height(), 1)
        for y in range(0, height, 2):
            self.create_rectangle(0, y, WIDTH, y + 2, outline="", fill=self._color_at(y))
        self.create_text(WIDTH / 2, 44, text=self.brand, fill="white",
                         font=theme.font(15, True))
        self.create_line(18, 76, WIDTH - 18, 76,
                         fill=theme.blend(theme.PRIMARY, "#ffffff", 0.35))

        self._rects, self._texts = [], []
        for i, (label, icon) in enumerate(self.items):
            top = 96 + i * ROW
            mid = top + 19
            tag = f"item{i}"
            rect = self.create_rectangle(12, top, WIDTH - 12, top + 38, outline="",
                                         fill=self._color_at(mid), tags=tag)
            self.create_image(34, mid, image=self.icons[icon], tags=tag)
            text = self.create_text(58, mid, text=label, anchor="w", fill="white",
                                    font=theme.font(10), tags=tag)
            self._rects.append((rect, mid))
            self._texts.append(text)
            self.tag_bind(tag, "<Button-1>", lambda _e, n=i: self.on_select(n))
            self.tag_bind(tag, "<Enter>", lambda _e, n=i: self._set_hover(n))
            self.tag_bind(tag, "<Leave>", lambda _e: self._set_hover(None))
        self._paint()

    def _paint(self):
        """Recolour the existing items; never create or delete anything here."""
        for i, (rect, mid) in enumerate(self._rects):
            base = self._color_at(mid)
            if i == self.active:
                fill = theme.blend(base, "#ffffff", 0.22)
            elif i == self.hover:
                fill = theme.blend(base, "#ffffff", 0.10)
            else:
                fill = base
            self.itemconfigure(rect, fill=fill)
            self.itemconfigure(self._texts[i], font=theme.font(10, i == self.active))

    def _set_hover(self, index):
        if index == self.hover:
            return
        self.hover = index
        self.configure(cursor="hand2" if index is not None else "")
        self._paint()
