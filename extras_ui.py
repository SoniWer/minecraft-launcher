"""Дополнительные окна лаунчера."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from java_download import JavaDownloadError, download_java, installed_java_path
from theme import theme_for_child
from tooltips import add_tooltip
from version_manager import InstalledVersion, delete_version, list_installed_versions


class VersionManagerWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, *, minecraft_dir: Path) -> None:
        super().__init__(parent)
        self.minecraft_dir = minecraft_dir
        self.title("Установленные версии Minecraft")
        self.geometry("520x360")

        columns = ("id", "type", "size")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("id", text="Версия")
        self.tree.heading("type", text="Тип")
        self.tree.heading("size", text="МБ")
        self.tree.column("id", width=220)
        self.tree.column("type", width=80)
        self.tree.column("size", width=60)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        row = ttk.Frame(self)
        row.pack(fill="x", padx=10, pady=6)
        for text, cmd, tip in (
            ("Обновить", self._reload, "Обновить список версий"),
            ("Удалить", self._delete, "Удалить выбранную версию с диска"),
        ):
            btn = ttk.Button(row, text=text, command=cmd)
            btn.pack(side="left", padx=4)
            add_tooltip(btn, tip)
        close_btn = ttk.Button(row, text="Закрыть", command=self.destroy)
        close_btn.pack(side="right")
        add_tooltip(close_btn, "Закрыть окно")

        theme_for_child(self, parent)
        self.transient(parent)
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
        mc_version: str,
        on_installed,
    ) -> None:
        super().__init__(parent)
        self.launcher_dir = launcher_dir
        self.on_installed = on_installed
        from java_manager import required_java_major

        self.major = required_java_major(mc_version)

        self.title("Скачать Java")
        self.geometry("400x160")
        ttk.Label(
            self,
            text=f"Скачать Eclipse Temurin Java {self.major} для Minecraft {mc_version}?",
            wraplength=360,
        ).pack(padx=12, pady=12)
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var).pack(padx=12)
        row = ttk.Frame(self)
        row.pack(pady=10)
        self.btn = ttk.Button(row, text="Скачать", command=self._start)
        self.btn.pack(side="left", padx=6)
        add_tooltip(self.btn, "Скачать Eclipse Temurin в папку лаунчера")
        cancel_btn = ttk.Button(row, text="Отмена", command=self.destroy)
        cancel_btn.pack(side="left")
        add_tooltip(cancel_btn, "Закрыть без установки")
        theme_for_child(self, parent)
        self.transient(parent)
        self.grab_set()

        existing = installed_java_path(launcher_dir, self.major)
        if existing:
            self.status_var.set(f"Уже установлена: {existing}")

    def _start(self) -> None:
        self.btn.configure(state="disabled")

        def worker() -> None:
            try:

                def status(t: str) -> None:
                    self.after(0, lambda: self.status_var.set(t))

                path = download_java(
                    self.launcher_dir, self.major, on_status=status
                )
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
