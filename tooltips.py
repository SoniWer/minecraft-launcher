"""Всплывающие подсказки при наведении."""

from __future__ import annotations

import tkinter as tk

from theme import FONTS


class ToolTip:
    def __init__(self, widget: tk.Misc, text: str, *, delay_ms: int = 450) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def set_text(self, text: str) -> None:
        self.text = (text or "").strip()

    def _on_enter(self, _event: object = None) -> None:
        if not self.text:
            return
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event: object = None) -> None:
        self._cancel()
        self._destroy()

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if not self.widget.winfo_exists():
            return
        self._destroy()
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        colors = getattr(self.widget.winfo_toplevel(), "_launcher_colors", None)
        if colors is not None:
            bg, fg, border = colors.entry, colors.fg, colors.muted
        else:
            bg, fg, border = "#2f2f36", "#ececec", "#555"
        label = tk.Label(
            tip,
            text=self.text,
            justify="left",
            background=bg,
            foreground=fg,
            relief="solid",
            borderwidth=1,
            highlightbackground=border,
            highlightthickness=1,
            font=FONTS["hint"],
            padx=7,
            pady=5,
            wraplength=300,
        )
        label.pack()
        self._window = tip

    def _destroy(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None


def add_tooltip(widget: tk.Misc, text: str, *, delay_ms: int = 450) -> ToolTip:
    return ToolTip(widget, text, delay_ms=delay_ms)
