"""Панель лога Minecraft (latest.log) в главном окне лаунчера."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import scrolledtext, ttk

from game_logs import latest_log
from theme import style_text_widget


class MinecraftLogPanel(ttk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        get_game_dir: Callable[[], Path],
        colors,
    ) -> None:
        super().__init__(parent, text="Лог Minecraft (latest.log)", padding=(6, 4))
        self.get_game_dir = get_game_dir
        self._colors = colors
        self._log_path: Path | None = None
        self._log_pos = 0
        self._fast_poll = False
        self._max_chars = 400_000

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 4))
        self.status_var = tk.StringVar(value="Запустите игру — лог появится здесь")
        ttk.Label(toolbar, textvariable=self.status_var, style="Hint.TLabel").pack(
            side="left"
        )
        ttk.Button(toolbar, text="Очистить экран", command=self._clear_view).pack(
            side="right"
        )

        self.text = scrolledtext.ScrolledText(
            self, wrap="none", height=6, font=("Consolas", 9), state="disabled"
        )
        self.text.pack(fill="both", expand=True)
        style_text_widget(self.text, colors)
        self._schedule_poll()

    def set_fast_poll(self, enabled: bool) -> None:
        self._fast_poll = enabled

    def reset_source(self) -> None:
        self._log_path = None
        self._log_pos = 0

    def _clear_view(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _append(self, chunk: str) -> None:
        if not chunk:
            return
        self.text.configure(state="normal")
        self.text.insert("end", chunk)
        if len(self.text.get("1.0", "end")) > 250_000:
            self.text.delete("1.0", "end-120000c")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        game_dir = self.get_game_dir()
        path = latest_log(game_dir)

        if path != self._log_path:
            self._log_path = path
            self._log_pos = 0
            self._clear_view()

        if not path or not path.is_file():
            self.status_var.set("Нет logs/latest.log — запустите Minecraft")
        else:
            try:
                size = path.stat().st_size
                if size < self._log_pos:
                    self._log_pos = 0
                    self._clear_view()
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(self._log_pos)
                    chunk = handle.read(self._max_chars)
                    self._log_pos = handle.tell()
                if chunk:
                    self._append(chunk)
                self.status_var.set(f"{path.name} · {size // 1024} КБ")
            except OSError as exc:
                self.status_var.set(f"Ошибка чтения: {exc}")

        delay = 400 if self._fast_poll else 2000
        self.after(delay, self._poll)

    def _schedule_poll(self) -> None:
        self.after(300, self._poll)
