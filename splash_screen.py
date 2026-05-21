"""Заставка при запуске лаунчера."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ui_assets import render_launcher_logo


def show_splash(parent: tk.Tk, on_done: Callable[[], None], *, duration_ms: int = 2200) -> None:
    colors = getattr(parent, "_launcher_colors", None)
    bg = colors.bg if colors else "#1a1a1e"
    fg = colors.fg if colors else "#ececec"
    accent = colors.accent if colors else "#3d9a4a"

    splash = tk.Toplevel(parent)
    splash.overrideredirect(True)
    splash.configure(bg=bg)
    splash.attributes("-topmost", True)

    w, h = 320, 200
    splash.update_idletasks()
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    px = max(0, (sw - w) // 2)
    py = max(0, (sh - h) // 2)
    splash.geometry(f"{w}x{h}+{px}+{py}")

    canvas = tk.Canvas(splash, width=w, height=h, bg=bg, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    logo = render_launcher_logo(96, master=splash)
    canvas.create_image(w // 2, 72, image=logo)
    splash._splash_logo = logo  # type: ignore[attr-defined]

    canvas.create_text(
        w // 2, 130, text="Minecraft Launcher", fill=fg, font=("Segoe UI", 14, "bold")
    )
    canvas.create_text(w // 2, 152, text="Загрузка…", fill=accent, font=("Segoe UI", 9))
    bar_bg = canvas.create_rectangle(40, 168, w - 40, 178, fill="#2f2f36", outline="")
    bar_fg = canvas.create_rectangle(40, 168, 40, 178, fill=accent, outline="")

    step = {"i": 0}

    def animate_bar() -> None:
        step["i"] = (step["i"] + 4) % (w - 80)
        x1 = 40 + step["i"]
        canvas.coords(bar_fg, 40, 168, min(x1 + 60, w - 40), 178)
        if splash.winfo_exists():
            splash.after(40, animate_bar)

    def fade_in(alpha: float = 0.0) -> None:
        if alpha >= 1.0:
            animate_bar()
            splash.after(duration_ms - 400, fade_out)
            return
        try:
            splash.attributes("-alpha", alpha)
        except tk.TclError:
            splash.after(max(0, duration_ms - 200), finish)
            return
        splash.after(30, lambda: fade_in(alpha + 0.12))

    def fade_out(alpha: float = 1.0) -> None:
        if alpha <= 0.0:
            finish()
            return
        try:
            splash.attributes("-alpha", alpha)
        except tk.TclError:
            finish()
            return
        splash.after(25, lambda: fade_out(alpha - 0.15))

    def finish() -> None:
        try:
            splash.destroy()
        except tk.TclError:
            pass
        on_done()

    splash.after(50, fade_in)
