"""Окно управления модами сборки."""

from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from theme import theme_for_child
from tooltips import add_tooltip
from ui_layout import BOTTOM_PAD, TOOLBAR_PAD, content_area, tree_with_scrollbar
from modrinth import (
    LOADER_IDS,
    ModUpdateInfo,
    ModrinthError,
    get_version,
    install_version_with_dependencies,
    scan_mod_updates,
)


class ModManagerWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        game_dir: Path,
        get_mc_version: Callable[[], str],
        get_loader_id: Callable[[], str],
        on_auto_backup: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.game_dir = game_dir
        self.mods_dir = game_dir / "mods"
        self.get_mc_version = get_mc_version
        self.get_loader_id = get_loader_id
        self.on_auto_backup = on_auto_backup

        self.title(f"Моды — {game_dir.name}")
        self.geometry("760x520")
        self.minsize(640, 460)

        self._entries: list[dict] = []
        self._updates: dict[str, ModUpdateInfo] = {}

        self._build_ui()
        theme_for_child(self, parent)
        self.transient(parent)
        self.grab_set()
        self._reload_list()

    def _modrinth_loader(self) -> str | None:
        loader_id = self.get_loader_id()
        if loader_id == "vanilla":
            return None
        return LOADER_IDS.get(loader_id)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=TOOLBAR_PAD[0], pady=TOOLBAR_PAD)
        bar = (
            ("Обновить", self._reload_list, "Перечитать папку mods/"),
            ("Проверить", self._check_updates, "Сравнить с Modrinth"),
            ("Обновить", self._update_selected, "Скачать новую версию мода"),
            ("Все", self._update_all, "Обновить все моды с доступным апдейтом"),
            ("Вкл.", self._enable_selected, "Убрать суффикс .disabled"),
            ("Выкл.", self._disable_selected, "Временно выключить мод"),
            ("Удалить", self._delete_selected, "Удалить файл мода с диска"),
        )
        for text, cmd, tip in bar:
            btn = ttk.Button(toolbar, text=text, style="Tool.TButton", command=cmd)
            btn.pack(side="left", padx=(0, 8))
            add_tooltip(btn, tip)

        list_frame = content_area(self)
        columns = ("name", "status", "version", "update")
        self.tree, _scroll = tree_with_scrollbar(
            list_frame, columns=columns, show="headings"
        )
        self.tree.heading("name", text="Файл")
        self.tree.heading("status", text="Статус")
        self.tree.heading("version", text="Версия / проект")
        self.tree.heading("update", text="Обновление")
        self.tree.column("name", width=200, stretch=True, minwidth=140)
        self.tree.column("status", width=88, stretch=False, anchor="center")
        self.tree.column("version", width=200, stretch=True)
        self.tree.column("update", width=150, stretch=False)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel", wraplength=700).pack(
            anchor="w", padx=BOTTOM_PAD[0], pady=(4, 0)
        )
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=BOTTOM_PAD[0], pady=BOTTOM_PAD)
        ttk.Button(footer, text="Закрыть", style="Tool.TButton", command=self.destroy).pack(
            side="right"
        )

    def _selected_entry(self) -> dict | None:
        selection = self.tree.selection()
        if not selection:
            return None
        iid = selection[0]
        for entry in self._entries:
            if entry["iid"] == iid:
                return entry
        return None

    def _list_mod_files(self) -> list[Path]:
        if not self.mods_dir.is_dir():
            self.mods_dir.mkdir(parents=True, exist_ok=True)
            return []
        files: list[Path] = []
        for path in sorted(self.mods_dir.iterdir()):
            if not path.is_file():
                continue
            lower = path.name.lower()
            if lower.endswith(".jar") or lower.endswith(".jar.disabled"):
                files.append(path)
        return files

    def _reload_list(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._entries.clear()
        self._updates.clear()

        for path in self._list_mod_files():
            disabled = path.name.endswith(".disabled")
            status = "выкл." if disabled else "вкл."
            info = self._updates.get(path.name)
            version_text = info.project_title if info else "—"
            if info and info.current_version:
                version_text = f"{info.project_title} ({info.current_version})"
            update_text = "—"
            if info and info.update_available and info.latest_version:
                update_text = f"→ {info.latest_version}"
            iid = self.tree.insert(
                "",
                "end",
                values=(path.name, status, version_text, update_text),
            )
            self._entries.append({"iid": iid, "path": path, "disabled": disabled})

        count = len(self._entries)
        self.status_var.set(f"Модов в папке: {count} · {self.mods_dir}")

    def _check_updates(self) -> None:
        mc_version = self.get_mc_version().strip()
        if not mc_version:
            messagebox.showwarning(
                "Внимание",
                "Выберите версию Minecraft на главном окне.",
                parent=self,
            )
            return

        self.status_var.set("Проверка обновлений на Modrinth...")

        def worker() -> None:
            try:
                results = scan_mod_updates(
                    self.mods_dir,
                    mc_version=mc_version,
                    loader=self._modrinth_loader(),
                )
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_check_error(e))
                return
            self.after(0, lambda r=results: self._on_check_done(r))

        threading.Thread(target=worker, daemon=True).start()

    def _on_check_error(self, exc: Exception) -> None:
        messagebox.showerror("Ошибка", str(exc), parent=self)
        self.status_var.set("Не удалось проверить обновления.")

    def _on_check_done(self, results: list[ModUpdateInfo]) -> None:
        self._updates = {item.filename: item for item in results}
        self._reload_list()
        available = sum(1 for item in results if item.update_available)
        known = sum(1 for item in results if item.project_id)
        self.status_var.set(
            f"На Modrinth распознано: {known} · доступно обновлений: {available}"
        )

    def _rename_mod(self, path: Path, enable: bool) -> Path | None:
        name = path.name
        if enable and name.endswith(".jar.disabled"):
            target = path.with_name(name[: -len(".disabled")])
        elif not enable and name.endswith(".jar") and not name.endswith(".disabled"):
            target = path.with_name(name + ".disabled")
        else:
            return path
        if target.exists():
            messagebox.showerror(
                "Ошибка", f"Файл уже существует:\n{target.name}", parent=self
            )
            return None
        path.rename(target)
        return target

    def _enable_selected(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        if not entry["disabled"]:
            return
        if self._rename_mod(entry["path"], True):
            self._reload_list()

    def _disable_selected(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        if entry["disabled"]:
            return
        if self._rename_mod(entry["path"], False):
            self._reload_list()

    def _delete_selected(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        if not messagebox.askyesno(
            "Удалить мод",
            f"Удалить «{entry['path'].name}»?",
            parent=self,
        ):
            return
        entry["path"].unlink(missing_ok=True)
        self._updates.pop(entry["path"].name, None)
        self._reload_list()

    def _update_selected(self) -> None:
        entry = self._selected_entry()
        if not entry:
            messagebox.showwarning("Внимание", "Выберите мод в списке.", parent=self)
            return
        info = self._updates.get(entry["path"].name)
        if not info or not info.update_available or not info.latest_version_id:
            messagebox.showinfo(
                "Обновление",
                "Сначала нажмите «Проверить обновления» и выберите мод с доступным обновлением.",
                parent=self,
            )
            return

        mc_version = self.get_mc_version().strip()
        if not mc_version:
            return

        self.status_var.set(f"Обновление {info.project_title}...")

        def worker() -> None:
            try:
                version = get_version(info.latest_version_id)
                if entry["path"].exists():
                    entry["path"].unlink()
                install_version_with_dependencies(
                    version,
                    minecraft_dir=self.game_dir,
                    project_type="mod",
                    mc_version=mc_version,
                    loader=self._modrinth_loader(),
                )
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_update_error(e))
                return
            self.after(0, lambda: self._on_update_done(info.project_title))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_error(self, exc: Exception) -> None:
        text = str(exc)
        if isinstance(exc, ModrinthError):
            text = f"Modrinth: {exc}"
        messagebox.showerror("Ошибка", text, parent=self)
        self.status_var.set("Ошибка обновления.")

    def _on_update_done(self, title: str) -> None:
        messagebox.showinfo("Готово", f"Мод обновлён: {title}", parent=self)
        self._check_updates()

    def _update_all(self) -> None:
        pending = [
            item
            for item in self._updates.values()
            if item.update_available and item.latest_version_id
        ]
        if not pending:
            messagebox.showinfo(
                "Обновление",
                "Нет доступных обновлений.\nСначала нажмите «Проверить обновления».",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Обновить все",
            f"Обновить {len(pending)} мод(ов) с Modrinth?\n\n"
            "Перед обновлением будет создан автобэкап сборки.",
            parent=self,
        ):
            return

        if self.on_auto_backup:
            self.on_auto_backup()

        mc_version = self.get_mc_version().strip()
        if not mc_version:
            return

        self.status_var.set(f"Обновление 0/{len(pending)}...")

        def worker() -> tuple[int, list[str]]:
            errors: list[str] = []
            done = 0
            path_by_name = {p.name: p for p in self._list_mod_files()}
            for index, info in enumerate(pending, start=1):

                def progress(i=index, total=len(pending), title=info.project_title) -> None:
                    self.after(
                        0,
                        lambda: self.status_var.set(
                            f"Обновление {i}/{total}: {title}..."
                        ),
                    )

                self.after(0, progress)
                try:
                    version = get_version(info.latest_version_id)
                    old = path_by_name.get(info.filename)
                    if old and old.exists():
                        old.unlink()
                    install_version_with_dependencies(
                        version,
                        minecraft_dir=self.game_dir,
                        project_type="mod",
                        mc_version=mc_version,
                        loader=self._modrinth_loader(),
                    )
                    done += 1
                except Exception as exc:
                    errors.append(f"{info.project_title}: {exc}")
            return done, errors

        def on_done(result: tuple[int, list[str]]) -> None:
            done, errors = result
            self._check_updates()
            if errors:
                messagebox.showwarning(
                    "Готово с ошибками",
                    f"Обновлено: {done}\n\n" + "\n".join(errors[:8]),
                    parent=self,
                )
            else:
                messagebox.showinfo(
                    "Готово", f"Обновлено модов: {done}", parent=self
                )

        def on_error(exc: Exception) -> None:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            self.status_var.set("Ошибка массового обновления.")

        def task() -> None:
            try:
                result = worker()
                self.after(0, lambda r=result: on_done(r))
            except Exception as exc:
                self.after(0, lambda e=exc: on_error(e))

        threading.Thread(target=task, daemon=True).start()
