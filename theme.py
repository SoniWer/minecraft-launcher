"""Тема и стили интерфейса лаунчера."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


@dataclass(frozen=True)
class ThemeColors:
    bg: str
    fg: str
    muted: str
    accent: str
    accent_hover: str
    accent_fg: str
    card: str
    entry: str
    border: str
    success: str
    danger: str


DARK = ThemeColors(
    bg="#1c1c1c",
    fg="#fafafa",
    muted="#a0a0a8",
    accent="#3d9a4a",
    accent_hover="#4db35c",
    accent_fg="#ffffff",
    card="#252525",
    entry="#2a2a2a",
    border="#3a3a44",
    success="#5ecf6a",
    danger="#e06060",
)

LIGHT = ThemeColors(
    bg="#eef0f4",
    fg="#1a1a1e",
    muted="#5c6370",
    accent="#2d7a38",
    accent_hover="#3a9a48",
    accent_fg="#ffffff",
    card="#ffffff",
    entry="#ffffff",
    border="#d0d4dc",
    success="#2d7a38",
    danger="#c0392b",
)

FONTS = {
    "title": ("Segoe UI", 22, "bold"),
    "subtitle": ("Segoe UI", 10),
    "section": ("Segoe UI", 9, "bold"),
    "body": ("Segoe UI", 10),
    "form": ("Segoe UI", 10),
    "hint": ("Segoe UI", 8),
    "mono": ("Consolas", 9),
    "play": ("Segoe UI", 13, "bold"),
}


def apply_theme(root: tk.Misc, *, dark: bool) -> ThemeColors:
    """Применить тему к окну и зарегистрировать флаг на root."""
    colors = DARK if dark else LIGHT
    root._launcher_dark = dark  # type: ignore[attr-defined]
    root._launcher_colors = colors  # type: ignore[attr-defined]

    if isinstance(root, tk.Tk) or isinstance(root, tk.Toplevel):
        root.configure(bg=colors.bg)

    if dark:
        _apply_sv_or_clam(root, colors, dark=True)
    else:
        _apply_sv_or_clam(root, colors, dark=False)

    _configure_styles(root, colors)
    _sync_ttk_backgrounds(root, colors)
    if _using_sv_ttk():
        _flatten_sv_ttk_layouts(ttk.Style(root), colors)
    return colors


_FLAT_LABEL_LAYOUT = [("Label.label", {"sticky": "w"})]
_FLAT_TOOL_BUTTON_LAYOUT = [("Button.label", {"sticky": "nswe"})]
_MENU_MENUBUTTON_LAYOUT = [
    (
        "Menubutton.padding",
        {
            "sticky": "nswe",
            "children": [
                ("Menubutton.label", {"side": "left", "expand": 1}),
                ("Menubutton.indicator", {"side": "right", "sticky": "ns"}),
            ],
        },
    ),
]


def _flatten_sv_ttk_layouts(style: ttk.Style, colors: ThemeColors) -> None:
    """Убрать clam Label.border и пустой спрайт Toolbutton — чёрные квадраты на Windows."""
    bg = colors.bg
    for name in (
        "TLabel",
        "Title.TLabel",
        "Subtitle.TLabel",
        "Form.TLabel",
        "Hint.TLabel",
        "Status.TLabel",
        "Success.TLabel",
        "TLabelframe.Label",
        "Card.TLabelframe.Label",
    ):
        try:
            style.layout(name, _FLAT_LABEL_LAYOUT)
            style.configure(name, background=bg, borderwidth=0)
        except tk.TclError:
            pass
    try:
        style.layout("TFrame", [])
        style.configure("TFrame", background=bg, borderwidth=0)
    except tk.TclError:
        pass
    try:
        style.layout("Tool.TButton", _FLAT_TOOL_BUTTON_LAYOUT)
        style.configure(
            "Tool.TButton",
            background=bg,
            borderwidth=0,
            focuscolor=bg,
            relief="flat",
        )
        style.map(
            "Tool.TButton",
            background=[("active", colors.card), ("pressed", colors.entry)],
        )
    except tk.TclError:
        pass
    try:
        style.layout("Menu.TMenubutton", _MENU_MENUBUTTON_LAYOUT)
        style.configure("Menu.TMenubutton", background=bg, borderwidth=0, focuscolor=bg)
        style.map(
            "Menu.TMenubutton",
            background=[("active", colors.card), ("pressed", colors.entry)],
        )
    except tk.TclError:
        pass


def _sync_ttk_backgrounds(root: tk.Misc, colors: ThemeColors) -> None:
    """Единый фон для всех ttk-элементов (после sv_ttk, иначе «чёрные квадраты»)."""
    style = ttk.Style(root)
    bg = colors.bg
    for name in (
        "TLabel",
        "TFrame",
        "TLabelframe",
        "TNotebook",
        "TNotebook.Tab",
        "Card.TLabelframe",
        "Card.TLabelframe.Label",
        "Title.TLabel",
        "Subtitle.TLabel",
        "Form.TLabel",
        "Hint.TLabel",
        "Status.TLabel",
        "Success.TLabel",
        "Tool.TButton",
        "Menu.TMenubutton",
        "Accent.TButton",
        "Stop.TButton",
        "Horizontal.TSeparator",
    ):
        try:
            style.configure(name, background=bg)
        except tk.TclError:
            pass
    try:
        style.configure("Card.TLabelframe", bordercolor=colors.border)
        style.configure("Tool.TButton", borderwidth=0)
    except tk.TclError:
        pass


def theme_for_child(
    window: tk.Toplevel,
    parent: tk.Misc,
    *,
    min_width: int = 520,
    min_height: int = 360,
) -> ThemeColors:
    """Согласовать дочернее окно с темой родителя и стандартными кнопками окна."""
    from ui_layout import setup_toplevel_window

    dark = getattr(parent, "_launcher_dark", True)
    colors = apply_theme(window, dark=dark)
    setup_toplevel_window(window, min_width=min_width, min_height=min_height)
    return colors


def style_canvas(canvas: tk.Canvas, colors: ThemeColors) -> None:
    canvas.configure(bg=colors.bg, highlightthickness=0, borderwidth=0)


def _apply_sv_or_clam(root: tk.Misc, colors: ThemeColors, *, dark: bool) -> None:
    if isinstance(root, (tk.Tk, tk.Toplevel)):
        try:
            import sv_ttk

            sv_ttk.set_theme("dark" if dark else "light")
            root.configure(bg=colors.bg)
            return
        except ImportError:
            pass
    if dark:
        _apply_clam_dark(root, colors)


def _apply_clam_dark(root: tk.Misc, colors: ThemeColors) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    bg, fg, entry = colors.bg, colors.fg, colors.entry
    style.configure(".", background=bg, foreground=fg, fieldbackground=entry)
    for name in (
        "TLabel",
        "TButton",
        "TEntry",
        "TCombobox",
        "TRadiobutton",
        "TCheckbutton",
        "TLabelframe",
        "Treeview",
        "TProgressbar",
        "TFrame",
        "TNotebook",
        "TSeparator",
    ):
        style.configure(name, background=bg, foreground=fg)
    style.configure("TLabelframe.Label", background=bg, foreground=fg)
    style.configure("TEntry", fieldbackground=entry)
    style.configure("TCombobox", fieldbackground=entry)
    style.configure("Treeview", fieldbackground=entry)
    style.map("TButton", background=[("active", colors.card)])


def _configure_styles(root: tk.Misc, colors: ThemeColors) -> None:
    style = ttk.Style(root)
    pad_btn = (18, 10)
    pad_tool = (12, 6)

    style.configure("TFrame", background=colors.bg)
    style.configure("TNotebook", background=colors.bg, borderwidth=0, tabmargins=(2, 4, 2, 0))
    style.configure("TNotebook.Tab", padding=(14, 6), font=FONTS["body"])
    style.configure(
        "Card.TLabelframe",
        background=colors.bg,
        foreground=colors.fg,
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=colors.bg,
        foreground=colors.muted,
        font=FONTS["section"],
    )
    style.configure(
        "Title.TLabel",
        background=colors.bg,
        foreground=colors.fg,
        font=FONTS["title"],
        borderwidth=0,
    )
    style.configure(
        "Subtitle.TLabel",
        background=colors.bg,
        foreground=colors.muted,
        font=FONTS["subtitle"],
    )
    style.configure(
        "Form.TLabel",
        background=colors.bg,
        foreground=colors.muted,
        font=FONTS["form"],
        borderwidth=0,
    )
    style.configure(
        "Hint.TLabel",
        background=colors.bg,
        foreground=colors.muted,
        font=FONTS["hint"],
    )
    style.configure(
        "Status.TLabel",
        background=colors.bg,
        foreground=colors.muted,
        font=FONTS["body"],
    )
    style.configure(
        "Success.TLabel",
        background=colors.bg,
        foreground=colors.success,
        font=FONTS["body"],
    )
    style.configure("Accent.TButton", font=FONTS["play"], padding=pad_btn)
    style.configure("Tool.TButton", padding=pad_tool, borderwidth=0)
    style.configure("Menu.TMenubutton", padding=pad_tool, borderwidth=0)
    style.configure("Danger.TButton", padding=pad_tool)
    style.configure("Stop.TButton", font=FONTS["play"], padding=pad_btn)
    style.configure("Treeview", rowheight=28, font=FONTS["body"])
    style.configure("Modrinth.Treeview", rowheight=40, font=FONTS["body"])
    style.configure("Horizontal.TSeparator", background=colors.border)
    style.configure("Vertical.TSeparator", background=colors.border)

    if not _using_sv_ttk():
        style.configure(
            "Accent.TButton",
            background=colors.accent,
            foreground=colors.accent_fg,
        )
        style.map(
            "Accent.TButton",
            background=[("active", colors.accent_hover), ("disabled", "#555")],
            foreground=[("disabled", "#aaa")],
        )
        style.configure(
            "Danger.TButton",
            background="#4a3030",
            foreground=colors.fg,
        )
        style.map("Danger.TButton", background=[("active", "#5c3838")])
        style.configure(
            "Stop.TButton",
            background=colors.danger,
            foreground=colors.accent_fg,
        )
        style.map(
            "Stop.TButton",
            background=[("active", "#f07070"), ("disabled", "#555")],
            foreground=[("disabled", "#aaa")],
        )


def _using_sv_ttk() -> bool:
    try:
        import sv_ttk  # noqa: F401

        return True
    except ImportError:
        return False


def style_text_widget(widget: tk.Text, colors: ThemeColors) -> None:
    widget.configure(
        bg=colors.entry,
        fg=colors.fg,
        insertbackground=colors.fg,
        selectbackground=colors.accent,
        selectforeground=colors.accent_fg,
        relief="flat",
        borderwidth=0,
    )
