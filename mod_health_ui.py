"""Окно результатов проверки mods/."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from mod_health import ModIssue, scan_mods_folder
from theme import theme_for_child
from ui_layout import autosize_toplevel, toplevel_shell, tree_with_scrollbar


class ModHealthWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, *, mods_dir: Path) -> None:
        super().__init__(parent)
        self.mods_dir = mods_dir
        self._issues = scan_mods_folder(mods_dir)
        self.title("Проверка модов")
        self._build_ui()
        autosize_toplevel(self, min_width=620, min_height=360)
        theme_for_child(self, parent)
        self.transient(parent)
        self.grab_set()

    def _build_ui(self) -> None:
        _shell, toolbar, body, footer = toplevel_shell(self)
        ttk.Label(
            toolbar,
            text=f"Папка: {self.mods_dir}",
            style="Hint.TLabel",
        ).pack(anchor="w")
        if not self._issues:
            ttk.Label(
                body,
                text="Проблем не найдено.",
                style="Status.TLabel",
            ).pack(anchor="w", padx=8, pady=8)
        else:
            self.tree, _scroll = tree_with_scrollbar(
                body, columns=("level", "message"), show="headings"
            )
            self.tree.heading("level", text="Уровень")
            self.tree.heading("message", text="Описание")
            self.tree.column("level", width=88, stretch=False)
            self.tree.column("message", width=480, stretch=True)
            self._issue_by_iid: dict[str, ModIssue] = {}
            for idx, issue in enumerate(self._issues):
                iid = f"issue_{idx}"
                self.tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(
                        "Ошибка" if issue.level == "error" else "Внимание",
                        issue.message,
                    ),
                    tags=(issue.kind,),
                )
                self._issue_by_iid[iid] = issue

        actions = ttk.Frame(footer)
        actions.grid(row=0, column=0, sticky="e")
        if self._issues:
            ttk.Button(
                actions,
                text="Удалить выбранный",
                style="Tool.TButton",
                command=self._delete_selected,
            ).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Закрыть", style="Tool.TButton", command=self.destroy).pack(
            side="right"
        )

    def _selected_issue(self) -> ModIssue | None:
        if not self._issues:
            return None
        sel = self.tree.selection()
        if not sel:
            return None
        return getattr(self, "_issue_by_iid", {}).get(sel[0])

    def _delete_selected(self) -> None:
        issue = self._selected_issue()
        if not issue or not issue.paths:
            messagebox.showinfo("Проверка модов", "Выберите строку в списке.", parent=self)
            return
        names = "\n".join(p.name for p in issue.paths)
        if not messagebox.askyesno(
            "Удалить файлы",
            f"Удалить?\n\n{names}",
            parent=self,
        ):
            return
        for path in issue.paths:
            path.unlink(missing_ok=True)
        parent = self.master
        self.destroy()
        ModHealthWindow(parent, mods_dir=self.mods_dir)
