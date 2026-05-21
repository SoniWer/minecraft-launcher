"""Диалог создания сборки с выбором версии Minecraft."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from theme import theme_for_child

LOADER_CHOICES = [
    ("vanilla", "Vanilla (без модов)"),
    ("fabric", "Fabric"),
    ("forge", "Forge"),
    ("neoforge", "NeoForge"),
    ("quilt", "Quilt"),
]


class NewBuildDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        mc_versions: list[str],
        default_mc: str = "",
        default_loader: str = "vanilla",
        on_created: Callable[[str, str, str], None],
    ) -> None:
        super().__init__(parent)
        self.on_created = on_created
        self.title("Новая сборка")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Название").grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        ttk.Entry(body, textvariable=self.name_var, width=32).grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Label(body, text="Версия MC").grid(row=1, column=0, sticky="w", pady=4)
        self.mc_var = tk.StringVar()
        mc_combo = ttk.Combobox(
            body,
            textvariable=self.mc_var,
            values=mc_versions,
            width=28,
            state="readonly" if mc_versions else "disabled",
        )
        mc_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)
        if default_mc and default_mc in mc_versions:
            self.mc_var.set(default_mc)
        elif mc_versions:
            self.mc_var.set(mc_versions[0])

        ttk.Label(body, text="Загрузчик").grid(row=2, column=0, sticky="w", pady=4)
        self.loader_var = tk.StringVar()
        labels = [label for _, label in LOADER_CHOICES]
        loader_combo = ttk.Combobox(
            body,
            textvariable=self.loader_var,
            values=labels,
            state="readonly",
            width=28,
        )
        loader_combo.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=4)
        display = next(
            (label for lid, label in LOADER_CHOICES if lid == default_loader),
            labels[0],
        )
        self.loader_var.set(display)

        body.columnconfigure(1, weight=1)

        row = ttk.Frame(body)
        row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(row, text="Отмена", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(row, text="Создать", command=self._submit).pack(side="right")

        theme_for_child(self, parent)
        self.bind("<Return>", lambda _e: self._submit())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _loader_id(self) -> str:
        label = self.loader_var.get()
        for lid, display in LOADER_CHOICES:
            if display == label:
                return lid
        return "vanilla"

    def _submit(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Внимание", "Введите название сборки.", parent=self)
            return
        mc = self.mc_var.get().strip()
        if not mc:
            messagebox.showwarning("Внимание", "Выберите версию Minecraft.", parent=self)
            return
        self.on_created(name, mc, self._loader_id())
        self.destroy()
