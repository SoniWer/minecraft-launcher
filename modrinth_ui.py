"""Окно поиска и скачивания контента с Modrinth."""

from __future__ import annotations

import concurrent.futures
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from theme import theme_for_child
from modrinth_icons import get_modrinth_icon
from modrinth import (
    CONTENT_FOLDERS,
    LOADER_IDS,
    InstallResult,
    ModpackInstallResult,
    ModrinthError,
    default_version_index,
    get_project_versions,
    install_modpack_version,
    install_version_with_dependencies,
    is_modpack_installed,
    is_stable_version,
    list_installed_filenames,
    pick_primary_file,
    project_is_installed,
    project_is_installed_modpack,
    search_projects,
    version_type_label,
)

CONTENT_TYPES: list[tuple[str, str]] = [
    ("mod", "Моды"),
    ("modpack", "Сборки (modpack)"),
    ("resourcepack", "Текстуры"),
    ("shader", "Шейдеры"),
]

POPULAR_LIMIT = 25

LOADER_FILTER_OPTIONS: list[tuple[str, str]] = [
    ("launcher", "Как в лаунчере"),
    ("any", "Любой"),
    ("fabric", "Fabric"),
    ("forge", "Forge"),
    ("neoforge", "NeoForge"),
    ("quilt", "Quilt"),
]
LOADER_FILTER_LABELS = [label for _, label in LOADER_FILTER_OPTIONS]
LOADER_FILTER_BY_LABEL = {label: key for key, label in LOADER_FILTER_OPTIONS}


class ModrinthBrowser(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        minecraft_dir: Path,
        shared_minecraft_dir: Path,
        get_mc_version: Callable[[], str],
        get_loader_id: Callable[[], str],
        on_modpack_installed: Callable[[dict[str, str]], None] | None = None,
        on_create_build_for_modpack: Callable[[str], Path] | None = None,
        on_auto_backup: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.minecraft_dir = minecraft_dir
        self.shared_dir = shared_minecraft_dir
        self.get_mc_version = get_mc_version
        self.get_loader_id = get_loader_id
        self.on_modpack_installed = on_modpack_installed
        self.on_create_build_for_modpack = on_create_build_for_modpack
        self.on_auto_backup = on_auto_backup

        self.title("Каталог Modrinth")
        self.geometry("740x540")
        self.minsize(660, 500)

        self._hits: list[dict] = []
        self._hit_by_iid: dict[str, dict] = {}
        self._versions: list[dict] = []
        self._search_offset = 0
        self._search_total = 0
        self._enrich_generation = 0

        self._build_ui()
        self._update_loader_filter_state()
        theme_for_child(self, parent)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(150, self._load_popular)

    def _is_alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _schedule_ui(self, callback: Callable[[], Any]) -> None:
        """Вызов UI только если окно ещё открыто (фоновые потоки)."""

        def run() -> None:
            if self._is_alive():
                callback()

        self.after(0, run)

    def _close(self) -> None:
        self._enrich_generation += 1
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 5}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Тип:").pack(side="left")
        self.type_var = tk.StringVar(value="Моды")
        type_combo = ttk.Combobox(
            top,
            textvariable=self.type_var,
            values=[label for _, label in CONTENT_TYPES],
            width=12,
            state="readonly",
        )
        type_combo.pack(side="left", padx=(4, 12))
        type_combo.bind("<<ComboboxSelected>>", self._on_type_changed)

        ttk.Label(top, text="Загрузчик:").pack(side="left", padx=(8, 0))
        self.loader_filter_var = tk.StringVar(value="Как в лаунчере")
        self.loader_filter_combo = ttk.Combobox(
            top,
            textvariable=self.loader_filter_var,
            values=LOADER_FILTER_LABELS,
            width=16,
            state="readonly",
        )
        self.loader_filter_combo.pack(side="left", padx=4)
        self.loader_filter_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._search(reset=True)
        )

        ttk.Label(top, text="Поиск:").pack(side="left", padx=(8, 0))
        self.query_var = tk.StringVar()
        query_entry = ttk.Entry(top, textvariable=self.query_var, width=32)
        query_entry.pack(side="left", padx=4)
        query_entry.bind("<Return>", lambda _e: self._search(reset=True))

        ttk.Button(top, text="Найти", command=lambda: self._search(reset=True)).pack(
            side="left", padx=4
        )
        self.more_btn = ttk.Button(
            top, text="Ещё", command=lambda: self._search(reset=False), state="disabled"
        )
        self.more_btn.pack(side="left")

        self.hint_mc_var = tk.StringVar()
        ttk.Label(self, textvariable=self.hint_mc_var, foreground="gray").pack(
            anchor="w", padx=10
        )
        self._update_search_hint()

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=4)

        columns = ("downloads", "description")
        self.tree = ttk.Treeview(
            list_frame, columns=columns, show="tree headings", selectmode="browse"
        )
        self.tree.heading("#0", text="Название")
        self.tree.heading("downloads", text="Скачивания")
        self.tree.heading("description", text="Описание")
        self.tree.column("#0", width=260, stretch=False)
        self.tree.column("downloads", width=90, stretch=False, anchor="center")
        self.tree.column("description", width=340)
        self.tree.tag_configure("installed", background="#c8e6c9", foreground="#1b5e20")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        detail = ttk.LabelFrame(self, text="Версия для установки")
        detail.pack(fill="x", padx=10, pady=4)
        self.version_combo = ttk.Combobox(detail, width=70, state="disabled")
        self.version_combo.pack(side="left", padx=8, pady=8)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=6)

        self.download_btn = ttk.Button(
            bottom,
            text="Скачать",
            command=self._download,
            state="disabled",
        )
        self._update_download_button_text()
        self.download_btn.pack(side="left")
        self.hint_label = ttk.Label(bottom, text="", font=("", 8), foreground="gray")
        self.hint_label.pack(side="left", padx=12)
        self._update_type_hint()
        ttk.Button(bottom, text="Закрыть", command=self._close).pack(side="right")

        self.status_var = tk.StringVar(value="Загрузка популярного контента...")
        ttk.Label(self, textvariable=self.status_var, wraplength=700).pack(
            anchor="w", padx=10, pady=2
        )
        self.progress = ttk.Progressbar(self, mode="determinate", length=700)
        self.progress.pack(fill="x", padx=10, pady=4)

    def _content_type(self) -> str:
        label = self.type_var.get()
        for type_id, display in CONTENT_TYPES:
            if display == label:
                return type_id
        return "mod"

    def _modrinth_loader(self) -> str | None:
        loader_id = self.get_loader_id()
        if loader_id == "vanilla":
            return None
        return LOADER_IDS.get(loader_id)

    def _api_loader(self) -> str | None:
        project_type = self._content_type()
        if project_type not in ("mod", "modpack"):
            return None

        choice = LOADER_FILTER_BY_LABEL.get(
            self.loader_filter_var.get(), "launcher"
        )
        if choice == "any":
            return None
        if choice == "launcher":
            return self._modrinth_loader()
        return LOADER_IDS.get(choice, choice)

    def _update_loader_filter_state(self) -> None:
        if self._content_type() in ("mod", "modpack"):
            self.loader_filter_combo.configure(state="readonly")
        else:
            self.loader_filter_combo.configure(state="disabled")

    def _update_search_hint(self) -> None:
        mc_version = self.get_mc_version() or "?"
        hint = f"Версия MC: {mc_version} · ✓ = уже установлено"
        project_type = self._content_type()
        if project_type in ("mod", "modpack"):
            loader = self._api_loader()
            filter_label = self.loader_filter_var.get()
            if loader:
                hint += f" · фильтр: {loader} ({filter_label})"
            else:
                hint += f" · фильтр загрузчика: {filter_label}"
        if self._is_alive():
            self.hint_mc_var.set(hint)

    def _update_type_hint(self) -> None:
        if self._content_type() == "modpack":
            text = "Создаётся новая сборка с именем modpack · стабильная по умолчанию"
        else:
            text = "По умолчанию — стабильная версия; бета — в списке вручную"
        if self._is_alive():
            self.hint_label.configure(text=text)

    def _update_download_button_text(self) -> None:
        if self._content_type() == "modpack":
            self.download_btn.configure(text="Установить сборку")
        else:
            self.download_btn.configure(text="Скачать")

    def _installed_files(self) -> set[str]:
        return list_installed_filenames(self.minecraft_dir, self._content_type())

    def _require_mc_version(self) -> str | None:
        mc_version = self.get_mc_version().strip()
        if not mc_version:
            messagebox.showwarning(
                "Внимание",
                "Сначала выберите версию Minecraft на главном окне лаунчера.",
                parent=self,
            )
            return None
        return mc_version

    def _load_popular(self) -> None:
        if self._require_mc_version():
            self._search(reset=True)

    def _on_type_changed(self, _event: object | None = None) -> None:
        self._update_type_hint()
        self._update_download_button_text()
        self._update_loader_filter_state()
        self._update_search_hint()
        self._clear_results()
        self._load_popular()

    def _clear_results(self) -> None:
        self._enrich_generation += 1
        self.tree.delete(*self.tree.get_children())
        self._hits.clear()
        self._hit_by_iid.clear()
        self._versions.clear()
        self.version_combo.set("")
        self.version_combo["values"] = []
        self.version_combo.configure(state="disabled")
        self.download_btn.configure(state="disabled")
        self._search_offset = 0
        self._search_total = 0
        self.more_btn.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self.download_btn.configure(
            state="disabled" if busy else ("normal" if self._versions else "disabled")
        )
        self.more_btn.configure(
            state="disabled"
            if busy
            else ("normal" if self._search_offset < self._search_total else "disabled")
        )

    def _format_title(self, hit: dict) -> str:
        title = hit.get("title", "?")
        if hit.get("_installed"):
            return f"✓ {title}"
        return title

    def _insert_hit(self, hit: dict) -> str:
        desc = (hit.get("description") or "").replace("\n", " ")
        if len(desc) > 120:
            desc = desc[:117] + "..."
        tags = ("installed",) if hit.get("_installed") else ()
        icon = get_modrinth_icon(hit.get("icon_url"), master=self)
        iid = self.tree.insert(
            "",
            "end",
            text=self._format_title(hit),
            image=icon if icon else "",
            values=(hit.get("downloads", 0), desc),
            tags=tags,
        )
        self._hit_by_iid[iid] = hit
        if not icon and hit.get("icon_url"):
            self._schedule_icon_load(iid, hit.get("icon_url"))
        return iid

    def _schedule_icon_load(self, iid: str, icon_url: str | None) -> None:
        if not icon_url:
            return

        def worker() -> None:
            icon = get_modrinth_icon(icon_url, master=self)

            def apply() -> None:
                if not self._is_alive():
                    return
                try:
                    if self.tree.exists(iid) and icon:
                        self.tree.item(iid, image=icon)
                except tk.TclError:
                    pass

            self._schedule_ui(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _update_hit_row(self, iid: str, hit: dict) -> None:
        if not self._is_alive():
            return
        try:
            if not self.tree.exists(iid):
                return
        except tk.TclError:
            return
        desc = (hit.get("description") or "").replace("\n", " ")
        if len(desc) > 120:
            desc = desc[:117] + "..."
        tags = ("installed",) if hit.get("_installed") else ()
        self.tree.item(
            iid,
            text=self._format_title(hit),
            values=(hit.get("downloads", 0), desc),
            tags=tags,
        )

    def _enrich_hits_async(self, items: list[tuple[str, dict]], generation: int) -> None:
        mc_version = self.get_mc_version().strip()
        project_type = self._content_type()
        loader = self._api_loader()
        installed_files = self._installed_files()

        def check_one(item: tuple[str, dict]) -> tuple[str, dict, bool]:
            iid, hit = item
            project_id = hit.get("project_id") or hit.get("slug")
            if not project_id:
                return iid, hit, False
            if project_type == "modpack":
                is_installed = project_is_installed_modpack(
                    self.minecraft_dir, project_id
                )
                filename = None
            else:
                is_installed, filename = project_is_installed(
                    project_id,
                    mc_version=mc_version,
                    project_type=project_type,
                    loader=loader,
                    installed_files=installed_files,
                )
            hit["_primary_filename"] = filename
            hit["_installed"] = is_installed
            return iid, hit, is_installed

        def worker() -> None:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(check_one, items))
            self._schedule_ui(
                lambda r=results, g=generation: self._apply_enrichment(r, g)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _apply_enrichment(
        self, results: list[tuple[str, dict, bool]], generation: int
    ) -> None:
        if not self._is_alive() or generation != self._enrich_generation:
            return
        installed_count = 0
        for iid, hit, is_installed in results:
            if is_installed:
                installed_count += 1
            self._update_hit_row(iid, hit)
            for stored in self._hits:
                if stored.get("project_id") == hit.get("project_id"):
                    stored["_installed"] = hit.get("_installed", False)
                    stored["_primary_filename"] = hit.get("_primary_filename")
        if installed_count:
            base = self.status_var.get().split("·")[0].strip()
            self.status_var.set(f"{base} · ✓ в списке: {installed_count}")

    def _search(self, *, reset: bool) -> None:
        mc_version = self._require_mc_version()
        if not mc_version:
            return

        if reset:
            self._clear_results()
            self._search_offset = 0

        query = self.query_var.get().strip()
        project_type = self._content_type()
        loader = self._api_loader()
        offset = self._search_offset
        generation = self._enrich_generation

        self._set_busy(True)
        label = "Популярное" if not query else "Поиск"
        self.status_var.set(f"{label} на Modrinth...")
        self.progress.configure(mode="indeterminate")
        self.progress.start(10)

        def worker() -> None:
            try:
                data = search_projects(
                    query=query,
                    project_type=project_type,
                    mc_version=mc_version,
                    loader=loader,
                    offset=offset,
                    limit=POPULAR_LIMIT,
                )
            except Exception as exc:
                self._schedule_ui(lambda e=exc: self._on_search_error(e))
                return
            self._schedule_ui(
                lambda d=data, g=generation: self._on_search_done(d, g)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_error(self, exc: Exception) -> None:
        if not self._is_alive():
            return
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self._set_busy(False)
        messagebox.showerror("Ошибка", f"Поиск не удался:\n{exc}", parent=self)

    def _on_search_done(self, data: dict, generation: int) -> None:
        if not self._is_alive() or generation != self._enrich_generation:
            return

        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100, value=0)
        self._set_busy(False)

        hits = data.get("hits") or []
        self._search_total = int(data.get("total_hits") or 0)
        self._search_offset += len(hits)

        new_items: list[tuple[str, dict]] = []
        for hit in hits:
            hit["_installed"] = False
            self._hits.append(hit)
            iid = self._insert_hit(hit)
            new_items.append((iid, hit))

        query = self.query_var.get().strip()
        project_type = self._content_type()
        if project_type == "modpack":
            folder_hint = "modpack → новая сборка с именем проекта"
        else:
            folder = CONTENT_FOLDERS.get(project_type, "mods")
            folder_hint = str(self.minecraft_dir / folder)
        prefix = "Популярное" if not query else "Найдено"
        self.status_var.set(
            f"{prefix}: {self._search_total} · показано {len(self._hits)} · {folder_hint}"
        )
        self.more_btn.configure(
            state="normal" if self._search_offset < self._search_total else "disabled"
        )

        if new_items:
            self._enrich_hits_async(new_items, generation)

    def _selected_hit(self) -> dict | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self._hit_by_iid.get(selection[0])

    def _on_select(self, _event: object | None = None) -> None:
        hit = self._selected_hit()
        if not hit:
            return

        mc_version = self._require_mc_version()
        if not mc_version:
            return

        project_id = hit.get("project_id") or hit.get("slug")
        if not project_id:
            return

        self.version_combo.configure(state="disabled")
        self.version_combo.set("")
        self.download_btn.configure(state="disabled")
        self.status_var.set(f"Загрузка версий: {hit.get('title', project_id)}...")

        def worker() -> None:
            try:
                project_type = self._content_type()
                versions = get_project_versions(
                    project_id,
                    mc_version=mc_version,
                    project_type=project_type,
                    loader=self._api_loader(),
                )
            except Exception as exc:
                self._schedule_ui(lambda e=exc: self._on_versions_error(e))
                return
            self._schedule_ui(
                lambda v=versions, h=hit: self._on_versions_loaded(v, h)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_versions_error(self, exc: Exception) -> None:
        if not self._is_alive():
            return
        self.status_var.set("Не удалось загрузить версии.")
        messagebox.showerror("Ошибка", str(exc), parent=self)

    def _on_versions_loaded(self, versions: list[dict], hit: dict) -> None:
        if not self._is_alive():
            return
        self._versions = versions
        installed_files = self._installed_files()
        project_type = self._content_type()
        project_id = hit.get("project_id") or ""
        labels: list[str] = []
        stable_count = 0
        for version in versions:
            primary = pick_primary_file(version) or {}
            fname = primary.get("filename", "")
            if project_type == "modpack":
                mark = (
                    "✓ "
                    if is_modpack_installed(
                        self.minecraft_dir, project_id, version.get("id")
                    )
                    else ""
                )
            else:
                mark = "✓ " if fname.lower() in installed_files else ""
            vtype = version.get("version_type", "")
            if is_stable_version(version):
                stable_count += 1
            type_text = version_type_label(vtype)
            labels.append(
                f"{mark}{version.get('name', version.get('version_number', '?'))} "
                f"({type_text})"
            )
        try:
            self.version_combo["values"] = labels
            if labels:
                default_idx = default_version_index(versions)
                if default_idx < 0:
                    default_idx = 0
                self.version_combo.current(default_idx)
                self.version_combo.configure(state="readonly")
                self.download_btn.configure(state="normal")
                extra = ""
                if stable_count == 0:
                    extra = " · только бета/альфа, выберите версию вручную"
                elif stable_count < len(versions):
                    extra = f" · стабильных: {stable_count}, остальное — вручную"
                self.status_var.set(
                    f"Версий: {len(labels)} · {hit.get('title', '')}{extra}"
                )
            else:
                self.version_combo.set("Нет версий для выбранной MC / загрузчика")
                self.download_btn.configure(state="disabled")
                self.status_var.set("Нет совместимых версий.")
        except tk.TclError:
            return

    def _selected_version(self) -> dict | None:
        if not self._versions:
            return None
        index = self.version_combo.current()
        if index < 0:
            index = 0
        if index >= len(self._versions):
            index = 0
        return self._versions[index]

    def _mark_project_installed(self, project_id: str, filename: str | None) -> None:
        if not project_id:
            return
        for iid, stored in self._hit_by_iid.items():
            if stored.get("project_id") == project_id:
                stored["_installed"] = True
                if filename:
                    stored["_primary_filename"] = filename
                self._update_hit_row(iid, stored)

    def _download(self) -> None:
        version = self._selected_version()
        hit = self._selected_hit()
        if not version or not hit:
            messagebox.showwarning("Внимание", "Выберите проект и версию.", parent=self)
            return

        project_type = self._content_type()
        mc_version = self._require_mc_version()
        if not mc_version:
            return

        title = hit.get("title", "файл")
        install_game_dir = self.minecraft_dir

        if project_type == "modpack":
            if self.on_auto_backup:
                self.on_auto_backup()
            if self.on_create_build_for_modpack:
                try:
                    install_game_dir = self.on_create_build_for_modpack(title)
                except Exception as exc:
                    messagebox.showerror(
                        "Ошибка",
                        f"Не удалось создать сборку:\n{exc}",
                        parent=self,
                    )
                    return
            self.status_var.set(f"Новая сборка «{title}» — установка...")

        self._set_busy(True)
        self.progress.configure(mode="determinate", maximum=100, value=0)
        self.status_var.set(f"Скачивание: {title}...")

        def progress(done: int, total: int | None) -> None:
            if total:
                percent = min(100, int(done * 100 / total))
                self._schedule_ui(
                    lambda p=percent: self.progress.configure(value=p)
                )

        def status(text: str) -> None:
            self._schedule_ui(lambda t=text: self.status_var.set(t))

        def worker() -> None:
            try:
                if project_type == "modpack":
                    modpack_result = install_modpack_version(
                        version,
                        game_dir=install_game_dir,
                        shared_dir=self.shared_dir,
                        on_progress=progress,
                        on_status=status,
                    )
                    self._schedule_ui(
                        lambda r=modpack_result, h=hit: self._on_modpack_done(r, h)
                    )
                    return
                install_results = install_version_with_dependencies(
                    version,
                    minecraft_dir=self.minecraft_dir,
                    project_type=project_type,
                    mc_version=mc_version,
                    loader=self._api_loader(),
                    on_progress=progress,
                    on_status=status,
                )
            except Exception as exc:
                self._schedule_ui(lambda e=exc: self._on_download_error(e))
                return
            self._schedule_ui(
                lambda r=install_results, h=hit: self._on_download_done(r, h)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_modpack_done(self, result: ModpackInstallResult, hit: dict) -> None:
        if not self._is_alive():
            return
        self._set_busy(False)
        self.progress.configure(value=100)
        self._mark_project_installed(result.project_id, result.filename)

        if result.skipped:
            self.status_var.set(f"Уже установлено: {result.filename}")
        else:
            self.status_var.set(f"Сборка установлена: {result.filename}")

        if self.on_modpack_installed and not result.skipped:
            self.on_modpack_installed(result.profile)

        profile = result.profile
        lines = [
            f"Новая сборка создана и настроена.",
            f"Modpack: {profile.get('name') or result.filename}",
            f"Minecraft: {profile.get('mc_version', '?')}",
            f"Загрузчик: {profile.get('loader', '?')}",
        ]
        if result.skipped:
            lines.insert(0, "Эта версия modpack уже была установлена в эту сборку.")
        else:
            lines.append(f"\nФайл: {result.path}")
        messagebox.showinfo("Готово", "\n".join(lines), parent=self)

        all_items = list(self._hit_by_iid.items())
        if all_items:
            self._enrich_hits_async(all_items, self._enrich_generation)

    def _on_download_error(self, exc: Exception) -> None:
        if not self._is_alive():
            return
        self._set_busy(False)
        self.progress.configure(value=0)
        text = str(exc)
        if isinstance(exc, ModrinthError):
            text = f"Modrinth: {exc}"
        messagebox.showerror("Ошибка", f"Не удалось скачать:\n{text}", parent=self)
        self.status_var.set("Ошибка скачивания.")

    def _on_download_done(self, results: list[InstallResult], hit: dict) -> None:
        if not self._is_alive():
            return
        self._set_busy(False)
        self.progress.configure(value=100)

        for item in results:
            if item.project_id:
                self._mark_project_installed(item.project_id, item.filename)

        downloaded = [r for r in results if not r.skipped]
        skipped = [r for r in results if r.skipped]

        if downloaded:
            names = ", ".join(r.filename for r in downloaded)
            self.status_var.set(f"Скачано: {names}")
        else:
            self.status_var.set("Всё уже было установлено")

        lines: list[str] = []
        if downloaded:
            lines.append("Скачано:")
            lines.extend(f"  • {r.filename}" for r in downloaded)
        if skipped:
            lines.append("Уже было:")
            lines.extend(f"  • {r.filename}" for r in skipped)

        messagebox.showinfo("Готово", "\n".join(lines) or "Готово", parent=self)

        all_items = list(self._hit_by_iid.items())
        if all_items:
            self._enrich_hits_async(all_items, self._enrich_generation)
