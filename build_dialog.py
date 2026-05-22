"""Диалог создания сборки с выбором версии Minecraft."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from theme import theme_for_child
from ui_layout import DIALOG_PAD, form_field, form_label, setup_form_grid

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

        body = ttk.Frame(self, padding=DIALOG_PAD)
        body.pack(fill="both", expand=True)
        setup_form_grid(body)

        form_label(body, 0, "Название")
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(body, textvariable=self.name_var, width=34)
        form_field(name_entry, 0)

        form_label(body, 1, "Версия MC")
        self.mc_var = tk.StringVar()
        mc_combo = ttk.Combobox(
            body,
            textvariable=self.mc_var,
            values=mc_versions,
            state="readonly" if mc_versions else "disabled",
        )
        form_field(mc_combo, 1)
        if default_mc and default_mc in mc_versions:
            self.mc_var.set(default_mc)
        elif mc_versions:
            self.mc_var.set(mc_versions[0])

        form_label(body, 2, "Загрузчик")
        self.loader_var = tk.StringVar()
        labels = [label for _, label in LOADER_CHOICES]
        loader_combo = ttk.Combobox(
            body,
            textvariable=self.loader_var,
            values=labels,
            state="readonly",
        )
        form_field(loader_combo, 2)
        display = next(
            (label for lid, label in LOADER_CHOICES if lid == default_loader),
            labels[0],
        )
        self.loader_var.set(display)

        row = ttk.Frame(body)
        row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(row, text="Отмена", style="Tool.TButton", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(row, text="Создать", style="Accent.TButton", command=self._submit).pack(
            side="right"
        )

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
