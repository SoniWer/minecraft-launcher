"""Логи и сбои — отдельное окно (открывается кнопкой на главном экране)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from datetime import datetime
from pathlib import Path

from app_paths import launcher_dir
from game_log_collector import GameLogCollector, read_persistent_game_log
from game_logs import list_crash_reports
from launcher_log import log_file_path
from theme import style_text_widget, theme_for_child
from ui_layout import autosize_toplevel, text_with_scrollbar, tree_with_scrollbar


class LogsAndCrashesWindow(tk.Toplevel):
    GAME_TAB = 1

    def __init__(
        self,
        parent: tk.Tk,
        *,
        get_game_dir: Callable[[], Path],
        get_shared_dir: Callable[[], Path] | None = None,
        log_collector: GameLogCollector | None = None,
        initial_tab: int = 1,
    ) -> None:
        super().__init__(parent)
        self.get_game_dir = get_game_dir
        self.get_shared_dir = get_shared_dir or (lambda: Path())
        self._collector = log_collector
        self.title("Логи и сбои")

        body = ttk.Frame(self, padding=(14, 12))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(body)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        tab_crash = ttk.Frame(self.notebook)
        self.notebook.add(tab_crash, text="  Crash-reports  ")
        list_frame = ttk.Frame(tab_crash)
        list_frame.pack(fill="both", expand=True)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        columns = ("name", "when", "size")
        self.tree, _scroll = tree_with_scrollbar(
            list_frame, columns=columns, show="headings"
        )
        self.tree.heading("name", text="Файл")
        self.tree.heading("when", text="Дата")
        self.tree.column("name", width=320, stretch=True)
        self.tree.column("when", width=140, stretch=False)
        self.tree.column("size", width=64, stretch=False, anchor="e")
        self.tree.bind("<Double-1>", self._open_crash_file)

        tab_game = ttk.Frame(self.notebook)
        self.notebook.add(tab_game, text="  Лог игры  ")
        self.game_log_text, _, _ = text_with_scrollbar(
            tab_game, wrap="none", height=20, font=("Consolas", 9), state="disabled"
        )

        tab_launcher = ttk.Frame(self.notebook)
        self.notebook.add(tab_launcher, text="  Лог лаунчера  ")
        self.launcher_log_text, _, _ = text_with_scrollbar(
            tab_launcher, wrap="none", height=20, font=("Consolas", 9), state="disabled"
        )

        colors = theme_for_child(self, parent, min_width=680, min_height=440)
        style_text_widget(self.game_log_text, colors)
        style_text_widget(self.launcher_log_text, colors)
        autosize_toplevel(self, min_width=720, min_height=460)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if self._collector:
            self._collector.add_listener(self._on_collector_update)

        if 0 <= initial_tab < self.notebook.index("end"):
            self.notebook.select(initial_tab)
        self._reload_crashes()
        self._reload_game_log()
        self._reload_launcher_log()

    def _on_close(self) -> None:
        if self._collector:
            self._collector.remove_listener(self._on_collector_update)
        self.destroy()

    def _on_collector_update(self) -> None:
        if not self.winfo_exists():
            return
        if self.notebook.index(self.notebook.select()) == self.GAME_TAB:
            self._reload_game_log(keep_scroll=False)

    def focus_game_tab(self) -> None:
        self.notebook.select(self.GAME_TAB)
        self._reload_game_log()

    def _reload_crashes(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for path, mtime, size_kb in list_crash_reports(self.get_game_dir()):
            when = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            self.tree.insert(
                "",
                "end",
                iid=str(path),
                values=(path.name, when, size_kb),
            )
        if not self.tree.get_children():
            self.tree.insert("", "end", iid="__empty", values=("Нет crash-reports", "", ""))

    def _set_text(self, widget: tk.Text, content: str, *, keep_scroll: bool) -> None:
        at_bottom = True
        if keep_scroll:
            try:
                at_bottom = float(widget.yview()[1]) >= 0.96
            except tk.TclError:
                at_bottom = True
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content or "(пусто)")
        if at_bottom:
            widget.see("end")
        widget.configure(state="disabled")

    def _reload_game_log(self, *, keep_scroll: bool = True) -> None:
        text = read_persistent_game_log(self.get_game_dir())
        if not text.strip():
            text = (
                "Здесь накапливается лог игры (.launcher/game_log.txt).\n"
                "Запустите Minecraft — новые строки появятся автоматически.\n"
                "Файл не очищается."
            )
        self._set_text(self.game_log_text, text, keep_scroll=keep_scroll)

    def _reload_launcher_log(self) -> None:
        from game_logs import read_log_tail

        path = log_file_path(launcher_dir())
        if path.is_file():
            text = f"# {path.name}\n\n{read_log_tail(path)}"
        else:
            text = "Файл launcher.log появится рядом с лаунчером."
        self._set_text(self.launcher_log_text, text, keep_scroll=True)

    def _open_crash_file(self, _event: object | None = None) -> None:
        from game_logs import open_file as open_log_file

        sel = self.tree.selection()
        if not sel or sel[0] == "__empty":
            return
        path = Path(sel[0])
        if not path.is_file():
            return
        try:
            open_log_file(path)
        except OSError:
            pass


CrashReportsWindow = LogsAndCrashesWindow
