"""Единые отступы, сетка форм и вспомогательные блоки интерфейса."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Отступы
SHELL_PAD = (16, 14)
TAB_PAD = (14, 12)
CARD_PAD = (14, 12)
DIALOG_PAD = (18, 16)
WINDOW_PAD = (14, 12)
TOOLBAR_PAD = (14, 10)
LIST_PAD = (14, 8)
BOTTOM_PAD = (14, 12)

# Форма (колонка подписи | поле)
LABEL_COL = 0
FIELD_COL = 1
LABEL_MIN = 124
FORM_ROW_PY = 6
LABEL_GAP = (0, 10)

# Кнопки в ряд
BTN_GAP = 6


def setup_form_grid(container: ttk.Misc, *, label_minsize: int = LABEL_MIN) -> None:
    container.columnconfigure(LABEL_COL, minsize=label_minsize, weight=0)
    container.columnconfigure(FIELD_COL, weight=1)


def form_label(parent: ttk.Misc, row: int, text: str) -> ttk.Label:
    lbl = ttk.Label(parent, text=text, style="Form.TLabel")
    lbl.grid(
        row=row,
        column=LABEL_COL,
        sticky="e",
        padx=LABEL_GAP,
        pady=FORM_ROW_PY,
    )
    return lbl


def form_field(widget: ttk.Widget | tk.Widget, row: int, *, columnspan: int = 1) -> None:
    widget.grid(
        row=row,
        column=FIELD_COL,
        columnspan=columnspan,
        sticky="ew",
        pady=FORM_ROW_PY,
    )


def form_hint(parent: ttk.Misc, row: int, variable: tk.Variable, *, columnspan: int = 2) -> ttk.Label:
    lbl = ttk.Label(parent, textvariable=variable, style="Hint.TLabel")
    lbl.grid(
        row=row,
        column=0,
        columnspan=columnspan,
        sticky="w",
        pady=(0, FORM_ROW_PY + 2),
    )
    return lbl


def app_header(parent: ttk.Misc, title: str, version: str) -> ttk.Frame:
    """Заголовок: название слева, версия справа, линия-разделитель."""
    frame = ttk.Frame(parent)
    frame.pack(fill="x", pady=(0, 10))
    frame.columnconfigure(0, weight=1)
    ttk.Label(frame, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=version, style="Subtitle.TLabel").grid(row=0, column=1, sticky="e")
    sep = ttk.Separator(frame, orient="horizontal")
    sep.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    return frame


def button_row(parent: ttk.Misc, buttons: list[tuple[str, object]], *, columns: int | None = None) -> ttk.Frame:
    """Равномерный ряд кнопок (uniform columns)."""
    cols = columns or len(buttons)
    row = ttk.Frame(parent)
    for c in range(cols):
        row.columnconfigure(c, weight=1, uniform="btnrow")
    for i, (text, cmd) in enumerate(buttons):
        btn = ttk.Button(row, text=text, command=cmd, style="Tool.TButton")
        pad = (0, BTN_GAP) if i < len(buttons) - 1 else (0, 0)
        btn.grid(row=0, column=i, sticky="ew", padx=pad)
    return row


def toolbar_frame(parent: ttk.Misc) -> ttk.Frame:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=TOOLBAR_PAD[0], pady=TOOLBAR_PAD)
    return bar


def content_area(parent: ttk.Misc) -> ttk.Frame:
    """Область списка/tree с отступами."""
    area = ttk.Frame(parent)
    area.pack(fill="both", expand=True, padx=LIST_PAD[0], pady=LIST_PAD)
    return area


def footer_bar(parent: ttk.Misc) -> ttk.Frame:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=BOTTOM_PAD[0], pady=BOTTOM_PAD)
    return bar


def tree_with_scrollbar(
    parent: ttk.Misc,
    *,
    columns: tuple[str, ...] | None = None,
    show: str = "headings",
    **tree_kw,
) -> tuple[ttk.Treeview, ttk.Scrollbar]:
    tree_kw.setdefault("selectmode", "browse")
    if columns:
        tree = ttk.Treeview(parent, columns=columns, show=show, **tree_kw)
    else:
        tree = ttk.Treeview(parent, show=show, **tree_kw)
    scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree, scroll
