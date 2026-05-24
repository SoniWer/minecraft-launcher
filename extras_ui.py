"""Дополнительные окна лаунчера."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from java_download import (
    JavaDownloadError,
    download_java,
    installed_java_path,
    list_installed_java_majors,
)
from theme import theme_for_child
from tooltips import add_tooltip
from ui_layout import WINDOW_PAD, tree_with_scrollbar
from version_manager import InstalledVersion, delete_version, list_installed_versions

JAVA_MAJOR_CHOICES = (8, 17, 21)


class VersionManagerWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, *, minecraft_dir: Path) -> None:
        super().__init__(parent)
        self.minecraft_dir = minecraft_dir
        self.title("Установленные версии Minecraft")
        self.geometry("600x480")

        shell = ttk.Frame(self, padding=WINDOW_PAD)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(shell)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        columns = ("id", "type", "size")
        self.tree, _scroll = tree_with_scrollbar(
            list_frame, columns=columns, show="headings"
        )
        self.tree.heading("id", text="Версия")
        self.tree.heading("type", text="Тип")
        self.tree.heading("size", text="МБ")
        self.tree.column("id", width=240, stretch=True)
        self.tree.column("type", width=88, stretch=False, anchor="center")
        self.tree.column("size", width=72, stretch=False, anchor="e")

        row = ttk.Frame(shell)
        row.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        for text, cmd, tip in (
            ("Обновить", self._reload, "Обновить список версий"),
            ("Удалить", self._delete, "Удалить выбранную версию с диска"),
        ):
            btn = ttk.Button(row, text=text, style="Tool.TButton", command=cmd)
            btn.pack(side="left", padx=(0, 8))
            add_tooltip(btn, tip)
        close_btn = ttk.Button(row, text="Закрыть", style="Tool.TButton", command=self.destroy)
        close_btn.pack(side="right")
        add_tooltip(close_btn, "Закрыть окно")

        theme_for_child(self, parent, min_width=520, min_height=420)
        self._reload()

    def _reload(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for item in list_installed_versions(self.minecraft_dir):
            self.tree.insert(
                "",
                "end",
                iid=item.version_id,
                values=(item.version_id, item.version_type, item.size_mb),
            )

    def _selected(self) -> InstalledVersion | None:
        sel = self.tree.selection()
        if not sel:
            return None
        vid = sel[0]
        for item in list_installed_versions(self.minecraft_dir):
            if item.version_id == vid:
                return item
        return None

    def _delete(self) -> None:
        item = self._selected()
        if not item:
            messagebox.showwarning("Внимание", "Выберите версию.", parent=self)
            return
        if not messagebox.askyesno(
            "Удалить",
            f"Удалить версию «{item.version_id}» ({item.size_mb} МБ)?",
            parent=self,
        ):
            return
        try:
            delete_version(self.minecraft_dir, item.version_id)
        except OSError as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        self._reload()


class JavaDownloadDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        launcher_dir: Path,
        suggested_major: int | None = None,
        mc_version: str = "",
        on_installed,
    ) -> None:
        super().__init__(parent)
        self.launcher_dir = launcher_dir
        self.on_installed = on_installed

        if suggested_major is None and mc_version.strip():
            from java_manager import required_java_major

            suggested_major = required_java_major(mc_version)
        if suggested_major not in JAVA_MAJOR_CHOICES:
            suggested_major = 21

        self.title("Скачать Java")
        self.geometry("480x220")
        body = ttk.Frame(self, padding=WINDOW_PAD)
        body.pack(fill="both", expand=True)

        hint = f" для Minecraft {mc_version}" if mc_version.strip() else ""
        ttk.Label(
            body,
            text=f"Eclipse Temurin (JRE) в папку лаунчера{hint}. Одна копия на версию Java.",
            wraplength=440,
        ).pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Версия Java:", style="Form.TLabel").pack(side="left")
        self.major_var = tk.StringVar(value=str(suggested_major))
        self.major_combo = ttk.Combobox(
            row,
            textvariable=self.major_var,
            values=[str(m) for m in JAVA_MAJOR_CHOICES],
            state="readonly",
            width=8,
        )
        self.major_combo.pack(side="left", padx=(10, 0))

        self.status_var = tk.StringVar(value="")
        ttk.Label(body, textvariable=self.status_var, style="Status.TLabel").pack(
            anchor="w"
        )

        btn_row = ttk.Frame(body)
        btn_row.pack(fill="x", pady=(14, 0))
        btn_row.columnconfigure(0, weight=1, uniform="dlgbtn")
        btn_row.columnconfigure(1, weight=1, uniform="dlgbtn")
        ttk.Button(btn_row, text="Отмена", style="Tool.TButton", command=self.destroy).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        self.btn = ttk.Button(btn_row, text="Скачать", style="Accent.TButton", command=self._start)
        self.btn.grid(row=0, column=1, sticky="ew")
        add_tooltip(self.btn, "Скачать только если этой версии ещё нет в папке java/")

        theme_for_child(self, parent, min_width=440, min_height=200)
        self.grab_set()
        self._refresh_installed_hint()

        self.major_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_installed_hint())

    def _selected_major(self) -> int:
        try:
            return int(self.major_var.get().strip())
        except ValueError:
            return 21

    def _refresh_installed_hint(self) -> None:
        major = self._selected_major()
        path = installed_java_path(self.launcher_dir, major)
        if path:
            self.status_var.set(f"Java {major} уже установлена: {path}")
        else:
            installed = list_installed_java_majors(self.launcher_dir)
            if installed:
                self.status_var.set(
                    f"Установлены: {', '.join(str(m) for m in installed)}. Java {major} — скачать."
                )
            else:
                self.status_var.set(f"Java {major} будет скачана в java/jdk-{major}/")

    def _start(self) -> None:
        major = self._selected_major()
        if major not in JAVA_MAJOR_CHOICES:
            messagebox.showwarning("Java", "Выберите 8, 17 или 21.", parent=self)
            return
        self.btn.configure(state="disabled")

        def worker() -> None:
            try:

                def status(t: str) -> None:
                    self.after(0, lambda: self.status_var.set(t))

                path = download_java(self.launcher_dir, major, on_status=status)
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_error(e))
                return
            self.after(0, lambda p=path: self._on_done(p))

        threading.Thread(target=worker, daemon=True).start()

    def _on_error(self, exc: Exception) -> None:
        self.btn.configure(state="normal")
        text = str(exc)
        if isinstance(exc, JavaDownloadError):
            text = str(exc)
        messagebox.showerror("Java", text, parent=self)

    def _on_done(self, java_path: Path) -> None:
        self.on_installed(str(java_path))
        messagebox.showinfo("Готово", f"Java установлена:\n{java_path}", parent=self)
        self.destroy()
