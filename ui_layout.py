"""Единые отступы, сетка форм и вспомогательные блоки интерфейса."""

from __future__ import annotations

import sys
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

# Главное окно: фиксированные высоты блока «Запуск», чтобы строки не прыгали
LAUNCH_STATUS_H = 22
LAUNCH_PATH_H = 34
LAUNCH_PLAY_TIME_H = 18


def ellipsize(text: str, max_len: int = 72) -> str:
    """Одна строка без переноса; длинный текст обрезается."""
    flat = " ".join(str(text).split())
    if len(flat) <= max_len:
        return flat
    return flat[: max_len - 1] + "…"


def reserve_grid_row(parent: ttk.Misc, row: int, height: int) -> None:
    """Фиксированная высота строки grid без tk.Frame (нет чёрных «пятен» на Windows)."""
    parent.rowconfigure(row, minsize=height)


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


def toplevel_shell(window: tk.Misc) -> tuple[ttk.Frame, ttk.Frame, ttk.Frame, ttk.Frame]:
    """
    Сетка для дочернего окна: панель инструментов, растягиваемое тело, нижний блок.
    Нижний блок не сжимается — кнопки «Закрыть» всегда видны.
    """
    shell = ttk.Frame(window, padding=WINDOW_PAD)
    shell.pack(fill="both", expand=True)
    shell.columnconfigure(0, weight=1)
    shell.rowconfigure(1, weight=1)

    toolbar = ttk.Frame(shell)
    toolbar.grid(row=0, column=0, sticky="ew", padx=TOOLBAR_PAD[0], pady=TOOLBAR_PAD)

    body = ttk.Frame(shell)
    body.grid(row=1, column=0, sticky="nsew")
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    footer = ttk.Frame(shell)
    footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    footer.columnconfigure(0, weight=1)
    return shell, toolbar, body, footer


def center_toplevel(
    window: tk.Misc,
    *,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Размещает окно по центру экрана (размеры — текущие или заданные)."""
    window.update_idletasks()
    w = width if width is not None else window.winfo_width()
    h = height if height is not None else window.winfo_height()
    if w < 100 or h < 100:
        return
    try:
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
    except tk.TclError:
        return
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2)
    window.geometry(f"{w}x{h}+{x}+{y}")


def setup_toplevel_window(
    window: tk.Misc,
    *,
    min_width: int = 520,
    min_height: int = 360,
) -> None:
    """Стандартное окно: можно менять размер, свернуть и развернуть на весь экран."""
    if not isinstance(window, (tk.Tk, tk.Toplevel)):
        return
    try:
        window.resizable(True, True)
        window.minsize(min_width, min_height)
        if sys.platform == "win32":
            window.attributes("-toolwindow", False)
    except tk.TclError:
        pass


def autosize_toplevel(
    window: tk.Misc,
    *,
    min_width: int = 520,
    min_height: int = 360,
    pad: int = 24,
    max_screen_fraction: float = 0.9,
) -> None:
    """Подгоняет размер окна под содержимое (после сборки виджетов)."""
    window.update_idletasks()
    req_w = window.winfo_reqwidth() + pad
    req_h = window.winfo_reqheight() + pad
    width = max(min_width, req_w)
    height = max(min_height, req_h)
    try:
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        width = min(width, int(sw * max_screen_fraction))
        height = min(height, int(sh * max_screen_fraction))
    except tk.TclError:
        pass
    window.geometry(f"{width}x{height}")
    setup_toplevel_window(window, min_width=min_width, min_height=min_height)


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


def text_with_scrollbar(
    parent: ttk.Misc,
    *,
    wrap: str = "word",
    height: int = 8,
    font: tuple[str, int] | None = None,
    **text_kw,
) -> tuple[tk.Text, ttk.Scrollbar, ttk.Frame]:
    """Текст с ttk.Scrollbar (как у списков в других окнах)."""
    frame = ttk.Frame(parent)
    kw: dict = {"wrap": wrap, "height": height, "borderwidth": 0}
    if font is not None:
        kw["font"] = font
    kw.update(text_kw)
    text = tk.Text(frame, **kw)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    frame.pack(fill="both", expand=True)
    return text, scroll, frame
