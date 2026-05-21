"""Панель скина и плаща в главном окне."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from skin_manager import (
    apply_skin_to_game,
    build_skin_paths,
    fetch_cape_bytes,
    fetch_skin_bytes,
    load_preview_image,
    save_cape_file,
    save_skin_file,
)
from theme import theme_for_child


class SkinPanel(ttk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        get_build_root: Callable[[], Path | None],
        get_game_dir: Callable[[], Path],
        get_username: Callable[[], str],
        on_changed: Callable[[], None],
    ) -> None:
        super().__init__(parent, text="Скин и плащ", padding=(6, 4))
        self.get_build_root = get_build_root
        self.get_game_dir = get_game_dir
        self.get_username = get_username
        self.on_changed = on_changed
        self._photo: tk.PhotoImage | None = None

        row = ttk.Frame(self)
        row.pack(fill="x")

        self.preview = tk.Label(row, text="?", width=4, anchor="center")
        self.preview.pack(side="left", padx=(0, 8))

        btns = ttk.Frame(row)
        btns.pack(side="left", fill="x", expand=True)
        ttk.Button(btns, text="Файл…", width=8, command=self._pick_skin).pack(
            fill="x", pady=1
        )
        ttk.Button(btns, text="По нику", width=8, command=self._fetch_skin).pack(
            fill="x", pady=1
        )
        ttk.Button(btns, text="Плащ…", width=8, command=self._pick_cape).pack(
            fill="x", pady=1
        )
        ttk.Button(btns, text="Плащ ник", width=8, command=self._fetch_cape).pack(
            fill="x", pady=1
        )

        self.hint_var = tk.StringVar(
            value="Нужен мод CustomSkinLoader в mods/"
        )
        ttk.Label(self, textvariable=self.hint_var, style="Hint.TLabel", wraplength=200).pack(
            anchor="w", pady=(4, 0)
        )

        self.refresh_preview()

    def refresh_preview(self) -> None:
        root = self.get_build_root()
        if root is None:
            self.preview.configure(image="", text="?")
            return
        skin_path, _cape = build_skin_paths(root)
        img = load_preview_image(skin_path if skin_path.is_file() else None)
        if img is None:
            self._photo = None
            self.preview.configure(image="", text="Steve")
            return
        from PIL import Image, ImageTk

        thumb = img.resize((48, 48), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(thumb)
        self.preview.configure(image=self._photo, text="")

    def _pick_skin(self) -> None:
        root = self.get_build_root()
        if root is None:
            return
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Файл скина (PNG)",
            filetypes=[("PNG", "*.png"), ("Все", "*.*")],
        )
        if not path:
            return
        try:
            data = Path(path).read_bytes()
            save_skin_file(root, data)
            self.on_changed()
            self.refresh_preview()
        except OSError as exc:
            messagebox.showerror("Скин", str(exc), parent=self.winfo_toplevel())

    def _pick_cape(self) -> None:
        root = self.get_build_root()
        if root is None:
            return
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Файл плаща (PNG)",
            filetypes=[("PNG", "*.png"), ("Все", "*.*")],
        )
        if not path:
            return
        try:
            data = Path(path).read_bytes()
            save_cape_file(root, data)
            self.on_changed()
            self.hint_var.set("Плащ сохранён · CustomSkinLoader")
        except OSError as exc:
            messagebox.showerror("Плащ", str(exc), parent=self.winfo_toplevel())

    def _fetch_cape(self) -> None:
        root = self.get_build_root()
        if root is None:
            return
        name = self.get_username()
        try:
            data = fetch_cape_bytes(name)
            save_cape_file(root, data)
            self.on_changed()
            self.hint_var.set(f"Плащ для {name}")
        except Exception as exc:
            messagebox.showerror("Плащ", str(exc), parent=self.winfo_toplevel())

    def _fetch_skin(self) -> None:
        root = self.get_build_root()
        if root is None:
            return
        name = self.get_username()
        try:
            data = fetch_skin_bytes(name)
            save_skin_file(root, data)
            self.on_changed()
            self.refresh_preview()
            self.hint_var.set(f"Скин для {name}")
        except Exception as exc:
            messagebox.showerror("Скин", str(exc), parent=self.winfo_toplevel())

    def apply_before_launch(self) -> None:
        build_root = self.get_build_root()
        if build_root is None:
            return
        apply_skin_to_game(
            self.get_game_dir(),
            build_root,
            username=self.get_username(),
        )


class SkinWindow(tk.Toplevel):
    """Расширенное окно скина (опционально)."""

    def __init__(self, parent: tk.Tk, panel: SkinPanel) -> None:
        super().__init__(parent)
        self.title("Скин и плащ")
        self.geometry("360x280")
        theme_for_child(self, parent)
        ttk.Label(
            self,
            text="Скин и плащ применяются через CustomSkinLoader.\n"
            "Установите мод в папку mods/ (Fabric/Forge).",
            wraplength=320,
        ).pack(padx=12, pady=12)
        ttk.Button(self, text="Закрыть", command=self.destroy).pack(pady=8)
