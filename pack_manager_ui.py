"""Список пакетов (моды, текстуры, шейдеры) с вкл./выкл."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from theme import theme_for_child
from tooltips import add_tooltip


@dataclass(frozen=True)
class PackKind:
    key: str
    folder: str
    title: str
    extensions: tuple[str, ...]


PACK_MODS = PackKind("mods", "mods", "Моды", (".jar",))
PACK_TEXTURES = PackKind("resourcepacks", "resourcepacks", "Текстуры", (".zip",))
PACK_SHADERS = PackKind("shaderpacks", "shaderpacks", "Шейдеры", (".zip",))


class PackListWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        game_dir: Path,
        kind: PackKind,
        modrinth_window_factory=None,
    ) -> None:
        super().__init__(parent)
        self.game_dir = game_dir
        self.kind = kind
        self.pack_dir = game_dir / kind.folder
        self.modrinth_window_factory = modrinth_window_factory

        self.title(f"{kind.title} — {game_dir.name}")
        self.geometry("640x380")
        self.minsize(520, 300)

        self._entries: list[dict] = []
        self._build_ui()
        theme_for_child(self, parent)
        self.transient(parent)
        self.grab_set()
        self._reload_list()

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=8)
        for text, cmd, tip in (
            ("Обновить", self._reload_list, "Перечитать папку"),
            ("Включить", self._enable_selected, "Снять .disabled"),
            ("Отключить", self._disable_selected, "Добавить .disabled"),
            ("Удалить", self._delete_selected, "Удалить файл"),
            ("Открыть папку", self._open_folder, f"Папка {self.kind.folder}"),
        ):
            btn = ttk.Button(toolbar, text=text, command=cmd)
            btn.pack(side="left", padx=(0, 6))
            add_tooltip(btn, tip)

        if self.kind.key == "mods" and self.modrinth_window_factory:
            ttk.Button(
                toolbar,
                text="Modrinth",
                command=self.modrinth_window_factory,
            ).pack(side="right")

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=4)

        self.tree = ttk.Treeview(
            list_frame, columns=("name", "status"), show="headings", selectmode="browse"
        )
        self.tree.heading("name", text="Файл")
        self.tree.heading("status", text="Статус")
        self.tree.column("name", width=420)
        self.tree.column("status", width=80, stretch=False)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, wraplength=600).pack(
            anchor="w", padx=10, pady=6
        )
        ttk.Button(self, text="Закрыть", command=self.destroy).pack(pady=6)

    def _selected_entry(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        for entry in self._entries:
            if entry["iid"] == iid:
                return entry
        return None

    def _matches_pack(self, path: Path) -> bool:
        lower = path.name.lower()
        for ext in self.kind.extensions:
            if lower.endswith(ext) or lower.endswith(ext + ".disabled"):
                return True
        return False

    def _list_files(self) -> list[Path]:
        self.pack_dir.mkdir(parents=True, exist_ok=True)
        return sorted(
            p for p in self.pack_dir.iterdir() if p.is_file() and self._matches_pack(p)
        )

    def _reload_list(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._entries.clear()
        for path in self._list_files():
            disabled = path.name.lower().endswith(".disabled")
            status = "выкл." if disabled else "вкл."
            iid = self.tree.insert("", "end", values=(path.name, status))
            self._entries.append({"iid": iid, "path": path, "disabled": disabled})
        self.status_var.set(
            f"{len(self._entries)} файл(ов) · {self.pack_dir}"
        )

    def _toggle(self, path: Path, enable: bool) -> Path | None:
        name = path.name
        lower = name.lower()
        if enable and lower.endswith(".disabled"):
            for ext in self.kind.extensions:
                suffix = ext + ".disabled"
                if lower.endswith(suffix):
                    target = path.with_name(name[: -len(".disabled")])
                    break
            else:
                return path
        elif not enable:
            for ext in self.kind.extensions:
                if lower.endswith(ext) and not lower.endswith(ext + ".disabled"):
                    target = path.with_name(name + ".disabled")
                    break
            else:
                return path
        else:
            return path
        if target.exists():
            messagebox.showerror(
                "Ошибка", f"Уже существует:\n{target.name}", parent=self
            )
            return None
        path.rename(target)
        return target

    def _enable_selected(self) -> None:
        entry = self._selected_entry()
        if entry and entry["disabled"] and self._toggle(entry["path"], True):
            self._reload_list()

    def _disable_selected(self) -> None:
        entry = self._selected_entry()
        if entry and not entry["disabled"] and self._toggle(entry["path"], False):
            self._reload_list()

    def _delete_selected(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        if messagebox.askyesno("Удалить", f"Удалить «{entry['path'].name}»?", parent=self):
            entry["path"].unlink(missing_ok=True)
            self._reload_list()

    def _open_folder(self) -> None:
        import os
        import subprocess
        import sys

        folder = self.pack_dir.resolve()
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", folder], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)
