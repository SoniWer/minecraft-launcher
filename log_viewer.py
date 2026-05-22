"""Окно просмотра latest.log."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

from game_logs import latest_log
from theme import style_text_widget, theme_for_child
from ui_layout import TOOLBAR_PAD, WINDOW_PAD


class LogViewerWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, *, game_dir: Path) -> None:
        super().__init__(parent)
        self.game_dir = game_dir
        self.log_path = latest_log(game_dir)

        self.title("Лог сборки (latest.log)")
        self.geometry("720x480")
        self.minsize(500, 300)

        shell = ttk.Frame(self, padding=WINDOW_PAD)
        shell.pack(fill="both", expand=True)

        toolbar = ttk.Frame(shell)
        toolbar.pack(fill="x", pady=TOOLBAR_PAD)
        ttk.Button(toolbar, text="Обновить", style="Tool.TButton", command=self._reload).pack(
            side="left", padx=(0, 8)
        )
        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Авто", variable=self.auto_var).pack(side="left", padx=(0, 12))
        self.status_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self.status_var, style="Hint.TLabel").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(toolbar, text="Закрыть", style="Tool.TButton", command=self.destroy).pack(
            side="right"
        )

        self.text = scrolledtext.ScrolledText(shell, wrap="none", font=("Consolas", 9))
        self.text.pack(fill="both", expand=True)

        colors = theme_for_child(self, parent)
        style_text_widget(self.text, colors)
        self.transient(parent)
        self._reload()
        self._schedule_auto()

    def _reload(self) -> None:
        self.log_path = latest_log(self.game_dir)
        self.text.delete("1.0", "end")
        if not self.log_path or not self.log_path.is_file():
            self.text.insert("end", "Файл logs/latest.log пока не создан.\nЗапустите игру.")
            self.status_var.set("Нет лога")
            return
        try:
            content = self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.text.insert("end", f"Ошибка чтения: {exc}")
            self.status_var.set("Ошибка")
            return
        if len(content) > 500_000:
            content = content[-500_000:]
            content = "... (показаны последние 500 КБ)\n" + content
        self.text.insert("end", content)
        self.text.see("end")
        self.status_var.set(str(self.log_path))

    def _schedule_auto(self) -> None:
        if self.auto_var.get():
            self._reload()
        if self.winfo_exists():
            self.after(2000, self._schedule_auto)
