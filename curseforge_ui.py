"""Каталог модов CurseForge."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from curseforge import CfFile, CfMod, CurseForgeClient, CurseForgeError
from theme import theme_for_child
from ui_async import run_background


class CurseForgeBrowser(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        api_key: str,
        game_dir: Path,
        get_mc_version: Callable[[], str],
        get_loader_id: Callable[[], str],
    ) -> None:
        super().__init__(parent)
        self.game_dir = game_dir
        self.get_mc_version = get_mc_version
        self.get_loader_id = get_loader_id
        self._client = CurseForgeClient(api_key)
        self._mods: list[CfMod] = []
        self._files: list[CfFile] = []

        self.title("Каталог CurseForge")
        self.geometry("720x520")
        self.minsize(600, 440)
        theme_for_child(self, parent)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        self.query_var = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.query_var)
        ent.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ent.bind("<Return>", lambda _e: self._search())
        ttk.Button(top, text="Найти", command=self._search).pack(side="left")

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        left = ttk.Frame(paned)
        paned.add(left, weight=2)
        self.mod_list = tk.Listbox(left, height=16, activestyle="none")
        self.mod_list.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(left, command=self.mod_list.yview)
        scroll.pack(side="right", fill="y")
        self.mod_list.configure(yscrollcommand=scroll.set)
        self.mod_list.bind("<<ListboxSelect>>", self._on_mod_select)

        right = ttk.Frame(paned)
        paned.add(right, weight=3)
        self.file_list = tk.Listbox(right, height=16, activestyle="none")
        self.file_list.pack(side="left", fill="both", expand=True)
        scroll2 = ttk.Scrollbar(right, command=self.file_list.yview)
        scroll2.pack(side="right", fill="y")
        self.file_list.configure(yscrollcommand=scroll2.set)

        self.status_var = tk.StringVar(value="Введите запрос и нажмите «Найти»")
        ttk.Label(self, textvariable=self.status_var, style="Hint.TLabel").pack(
            anchor="w", padx=8
        )
        ttk.Button(self, text="Скачать в mods/", command=self._download).pack(pady=8)

        self.transient(parent)
        self.grab_set()

    def _search(self) -> None:
        q = self.query_var.get().strip()
        if not q:
            return
        self.status_var.set("Поиск…")

        def worker() -> list[CfMod]:
            return self._client.search_mods(
                q,
                game_version=self.get_mc_version(),
                loader_id=self.get_loader_id(),
            )

        def done(mods: list[CfMod]) -> None:
            self._mods = mods
            self.mod_list.delete(0, "end")
            for m in mods:
                self.mod_list.insert("end", f"{m.name}  ({m.download_count:,})")
            self.status_var.set(f"Найдено: {len(mods)}")

        def err(exc: Exception) -> None:
            messagebox.showerror("CurseForge", str(exc), parent=self)
            self.status_var.set("Ошибка поиска")

        run_background(self, worker, done, on_error=err)

    def _on_mod_select(self, _event: object | None = None) -> None:
        sel = self.mod_list.curselection()
        if not sel:
            return
        mod = self._mods[sel[0]]
        self.status_var.set(f"Файлы: {mod.name}…")

        def worker() -> list[CfFile]:
            return self._client.mod_files(mod.id, self.get_mc_version())

        def done(files: list[CfFile]) -> None:
            self._files = files
            self.file_list.delete(0, "end")
            for f in files:
                self.file_list.insert("end", f.display_name or f.file_name)
            self.status_var.set(f"Файлов: {len(files)}")

        run_background(self, worker, done, on_error=lambda e: messagebox.showerror("CurseForge", str(e), parent=self))

    def _download(self) -> None:
        fsel = self.file_list.curselection()
        if not fsel or not self._files:
            messagebox.showinfo("CurseForge", "Выберите файл.", parent=self)
            return
        cf = self._files[fsel[0]]
        dest_dir = self.game_dir / "mods"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / cf.file_name
        self.status_var.set("Скачивание…")

        def worker() -> Path:
            import requests

            resp = requests.get(cf.download_url, timeout=120)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return dest

        def done(path: Path) -> None:
            self.status_var.set(f"Сохранено: {path.name}")
            messagebox.showinfo("CurseForge", f"Установлено:\n{path}", parent=self)

        run_background(self, worker, done, on_error=lambda e: messagebox.showerror("CurseForge", str(e), parent=self))
