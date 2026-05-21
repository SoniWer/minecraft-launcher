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
    success: str
    danger: str


DARK = ThemeColors(
    bg="#1a1a1e",
    fg="#ececec",
    muted="#8a8f98",
    accent="#3d9a4a",
    accent_hover="#4db35c",
    accent_fg="#ffffff",
    card="#25252b",
    entry="#2f2f36",
    success="#5ecf6a",
    danger="#e06060",
)

LIGHT = ThemeColors(
    bg="#f0f2f5",
    fg="#1a1a1e",
    muted="#5c6370",
    accent="#2d7a38",
    accent_hover="#3a9a48",
    accent_fg="#ffffff",
    card="#ffffff",
    entry="#ffffff",
    success="#2d7a38",
    danger="#c0392b",
)

FONTS = {
    "title": ("Segoe UI", 20, "bold"),
    "subtitle": ("Segoe UI", 9),
    "section": ("Segoe UI", 9, "bold"),
    "body": ("Segoe UI", 10),
    "hint": ("Segoe UI", 8),
    "mono": ("Consolas", 9),
    "play": ("Segoe UI", 12, "bold"),
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
    return colors


def theme_for_child(window: tk.Toplevel, parent: tk.Misc) -> ThemeColors:
    """Согласовать дочернее окно с темой родителя."""
    dark = getattr(parent, "_launcher_dark", True)
    return apply_theme(window, dark=dark)


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
    ):
        style.configure(name, background=bg, foreground=fg)
    style.configure("TLabelframe.Label", background=bg, foreground=fg)
    style.configure("TEntry", fieldbackground=entry)
    style.configure("TCombobox", fieldbackground=entry)
    style.configure("Treeview", fieldbackground=entry)
    style.map("TButton", background=[("active", colors.card)])


def _configure_styles(root: tk.Misc, colors: ThemeColors) -> None:
    style = ttk.Style(root)
    pad_btn = (14, 8)
    pad_tool = (10, 4)

    style.configure("TFrame", background=colors.bg)
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
    )
    style.configure(
        "Subtitle.TLabel",
        background=colors.bg,
        foreground=colors.muted,
        font=FONTS["subtitle"],
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
    style.configure(
        "Accent.TButton",
        font=FONTS["play"],
        padding=pad_btn,
    )
    style.configure("Tool.TButton", padding=pad_tool)
    style.configure("Danger.TButton", padding=pad_tool)

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
