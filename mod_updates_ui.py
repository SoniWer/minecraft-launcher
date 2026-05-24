"""Окно проверки и обновления модов через Modrinth."""

from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from modrinth import (
    ModUpdateInfo,
    ModrinthError,
    apply_all_mod_updates,
    scan_mod_updates,
)
from theme import theme_for_child
from ui_layout import autosize_toplevel, toplevel_shell, tree_with_scrollbar


class ModUpdatesWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        game_dir: Path,
        mc_version: str,
        loader_id: str,
        on_auto_backup: Callable[[], object] | None = None,
        on_busy: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.game_dir = game_dir
        self.mc_version = mc_version.strip()
        self.loader_id = loader_id.strip()
        self.loader = None if self.loader_id in ("", "vanilla") else self.loader_id
        self.on_auto_backup = on_auto_backup
        self.on_busy = on_busy

        self._updates: list[ModUpdateInfo] = []
        self._busy = False

        self.title("Обновление модов (Modrinth)")
        self._build_ui()
        autosize_toplevel(self, min_width=640, min_height=400)
        theme_for_child(self, parent)
        self.transient(parent)
        self.grab_set()
        self.after(100, self._scan)

    def _build_ui(self) -> None:
        shell, toolbar, body, footer = toplevel_shell(self)
        ttk.Button(
            toolbar, text="Проверить снова", style="Tool.TButton", command=self._scan
        ).pack(side="left", padx=(0, 8))
        self.update_btn = ttk.Button(
            toolbar,
            text="Обновить все",
            style="Accent.TButton",
            command=self._update_all,
            state="disabled",
        )
        self.update_btn.pack(side="left")

        self.tree, _scroll = tree_with_scrollbar(
            body,
            columns=("mod", "current", "latest"),
            show="headings",
        )
        self.tree.heading("mod", text="Мод")
        self.tree.heading("current", text="Сейчас")
        self.tree.heading("latest", text="Доступно")
        self.tree.column("mod", width=260, stretch=True)
        self.tree.column("current", width=120, stretch=False)
        self.tree.column("latest", width=120, stretch=False)

        self.status_var = tk.StringVar(value="Проверка модов…")
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel", wraplength=560).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        actions = ttk.Frame(footer)
        actions.grid(row=1, column=0, sticky="e")
        ttk.Button(actions, text="Закрыть", style="Tool.TButton", command=self.destroy).pack(
            side="right"
        )

    def _mods_dir(self) -> Path:
        return self.game_dir / "mods"

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if self.on_busy:
            self.on_busy(busy)
        state = "disabled" if busy else "normal"
        self.update_btn.configure(state=state if self._count_updates() else "disabled")

    def _count_updates(self) -> int:
        return sum(1 for u in self._updates if u.update_available)

    def _scan(self) -> None:
        if self._busy:
            return
        if not self.mc_version:
            self.status_var.set("Выберите версию Minecraft в главном окне.")
            return
        self.status_var.set("Сканирование mods/…")
        self.tree.delete(*self.tree.get_children())
        self.update_btn.configure(state="disabled")

        def worker() -> list[ModUpdateInfo]:
            return scan_mod_updates(
                self._mods_dir(),
                mc_version=self.mc_version,
                loader=self.loader,
            )

        def done(items: list[ModUpdateInfo]) -> None:
            if not self.winfo_exists():
                return
            self._updates = items
            self.tree.delete(*self.tree.get_children())
            for info in items:
                if not info.update_available:
                    continue
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        info.project_title or info.filename,
                        info.current_version,
                        info.latest_version or "?",
                    ),
                )
            count = self._count_updates()
            total = len(items)
            if count:
                self.status_var.set(f"Доступно обновлений: {count} из {total} модов Modrinth")
                self.update_btn.configure(state="normal")
            else:
                self.status_var.set(
                    f"Все моды актуальны ({total} проверено)" if total else "В папке mods/ нет .jar"
                )

        def run() -> None:
            try:
                result = worker()
            except ModrinthError as exc:
                self.after(0, lambda: messagebox.showerror("Modrinth", str(exc), parent=self))
                self.after(0, lambda: self.status_var.set("Ошибка проверки"))
                return
            except Exception as exc:
                self.after(
                    0,
                    lambda: messagebox.showerror("Ошибка", str(exc), parent=self),
                )
                self.after(0, lambda: self.status_var.set("Ошибка проверки"))
                return
            self.after(0, lambda: done(result))

        threading.Thread(target=run, daemon=True).start()

    def _update_all(self) -> None:
        pending = [u for u in self._updates if u.update_available]
        if not pending:
            return
        if not messagebox.askyesno(
            "Обновить моды",
            f"Скачать обновления для {len(pending)} мод(ов)?\n"
            "Рекомендуется бэкап сборки.",
            parent=self,
        ):
            return
        if self.on_auto_backup:
            self.on_auto_backup()
        self._set_busy(True)
        self.status_var.set("Обновление…")

        def worker() -> list:
            return apply_all_mod_updates(
                pending,
                game_dir=self.game_dir,
                mc_version=self.mc_version,
                loader=self.loader,
                on_status=lambda t: self.after(0, lambda text=t: self.status_var.set(text)),
            )

        def finish(_results: list) -> None:
            if not self.winfo_exists():
                return
            self._set_busy(False)
            messagebox.showinfo(
                "Готово",
                f"Обновлено модов: {len(pending)}",
                parent=self,
            )
            self._scan()

        def run() -> None:
            try:
                results = worker()
            except ModrinthError as exc:
                self.after(
                    0,
                    lambda: (
                        self._set_busy(False),
                        messagebox.showerror("Modrinth", str(exc), parent=self),
                    ),
                )
                return
            except Exception as exc:
                self.after(
                    0,
                    lambda: (
                        self._set_busy(False),
                        messagebox.showerror("Ошибка", str(exc), parent=self),
                    ),
                )
                return
            self.after(0, lambda: finish(results))

        threading.Thread(target=run, daemon=True).start()
