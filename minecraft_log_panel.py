"""Панель лога Minecraft (latest.log) в главном окне лаунчера."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from game_logs import latest_log, read_log_incremental
from theme import style_text_widget


class MinecraftLogPanel(ttk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        get_game_dir: Callable[[], Path],
        colors,
    ) -> None:
        super().__init__(parent, text="Лог Minecraft", padding=(4, 4))
        self.get_game_dir = get_game_dir
        self._colors = colors
        self._log_path: Path | None = None
        self._log_pos = 0
        self._fast_poll = False
        self._stick_to_bottom = True
        self._poll_job: str | None = None
        self._last_status = ""

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 4))

        self.status_var = tk.StringVar(value="Запустите игру")
        ttk.Label(toolbar, textvariable=self.status_var, style="Hint.TLabel").pack(
            side="left"
        )

        ttk.Button(toolbar, text="Копировать", command=self._copy_log).pack(
            side="right", padx=(4, 0)
        )
        ttk.Button(toolbar, text="Очистить", command=self._clear_view).pack(
            side="right", padx=(4, 0)
        )

        self.text = scrolledtext.ScrolledText(
            self, wrap="word", height=5, font=("Consolas", 9), state="disabled"
        )
        self.text.pack(fill="both", expand=True)
        style_text_widget(self.text, colors)
        self.text.bind("<Button-1>", self._on_user_scroll)
        self.text.bind("<MouseWheel>", self._on_user_scroll)
        self.text.bind("<Key>", self._on_user_scroll)

        self._schedule_poll()

    def set_fast_poll(self, enabled: bool) -> None:
        self._fast_poll = enabled

    def reset_source(self) -> None:
        self._log_path = None
        self._log_pos = 0
        self._stick_to_bottom = True

    def _on_user_scroll(self, _event: object | None = None) -> None:
        if self._is_at_bottom():
            self._stick_to_bottom = True
        else:
            self._stick_to_bottom = False

    def _is_at_bottom(self) -> bool:
        try:
            return float(self.text.yview()[1]) >= 0.96
        except tk.TclError:
            return True

    def _set_status(self, text: str) -> None:
        if text != self._last_status:
            self._last_status = text
            self.status_var.set(text)

    def _clear_view(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._stick_to_bottom = True

    def _copy_log(self) -> None:
        content = self.text.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showinfo("Лог", "Нечего копировать.", parent=self.winfo_toplevel())
            return
        root = self.winfo_toplevel()
        try:
            root.clipboard_clear()
            root.clipboard_append(content)
            root.update_idletasks()
            self._set_status("Скопировано в буфер обмена")
        except tk.TclError as exc:
            messagebox.showerror("Лог", f"Не удалось скопировать:\n{exc}", parent=root)

    def _append(self, chunk: str) -> None:
        if not chunk:
            return
        at_bottom = self._is_at_bottom()
        self.text.configure(state="normal")
        self.text.insert("end", chunk)
        if len(self.text.get("1.0", "end")) > 200_000:
            self.text.delete("1.0", "end-80000c")
        if self._stick_to_bottom or at_bottom:
            self.text.see("end")
            self._stick_to_bottom = True
        self.text.configure(state="disabled")

    def _poll(self) -> None:
        if not self.winfo_ismapped():
            self._poll_job = self.after(800, self._poll)
            return

        game_dir = self.get_game_dir()
        path = latest_log(game_dir)

        if path != self._log_path:
            self._log_path = path
            self._log_pos = 0
            self._clear_view()

        if not path:
            self._set_status("Нет logs/ — запустите Minecraft")
        else:
            chunk, new_pos, err = read_log_incremental(path, self._log_pos)
            if err:
                self._set_status(f"Лог занят игрой — повтор… ({err[:40]})")
            else:
                self._log_pos = new_pos
                if chunk:
                    self._append(chunk)
                try:
                    kb = path.stat().st_size // 1024
                    self._set_status(f"{path.name} · {kb} КБ")
                except OSError:
                    self._set_status(path.name)

        delay = 350 if self._fast_poll else 1200
        self._poll_job = self.after(delay, self._poll)

    def _schedule_poll(self) -> None:
        self._poll_job = self.after(400, self._poll)

    def destroy(self) -> None:
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except tk.TclError:
                pass
        super().destroy()
