"""Снятие выделения текста в полях после программного изменения."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def clear_text_selection(widget: tk.Misc) -> None:
    try:
        if isinstance(widget, (ttk.Combobox, tk.Entry)):
            widget.selection_clear()
            widget.icursor("end")
        elif isinstance(widget, tk.Text):
            widget.tag_remove("sel", "1.0", "end")
    except tk.TclError:
        pass


def install_no_autoselect(widget: tk.Misc, variable: tk.Variable | None = None) -> None:
    """Не подсвечивать весь текст после set() / смены значения."""

    def defer_clear(_event: object | None = None) -> None:
        try:
            if widget.winfo_exists():
                widget.after_idle(lambda: clear_text_selection(widget))
        except tk.TclError:
            pass

    widget.bind("<FocusIn>", defer_clear, add="+")
    widget.bind("<<ComboboxSelected>>", defer_clear, add="+")
    if variable is not None:
        variable.trace_add("write", lambda *_: defer_clear())
