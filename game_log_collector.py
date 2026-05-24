"""Накопление лога игры в файл сборки (без очистки)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from game_logs import read_log_incremental, resolve_log_file

_MAX_DISPLAY_BYTES = 400_000


def persistent_game_log_path(game_dir: Path) -> Path:
    path = game_dir / ".launcher" / "game_log.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_game_log_line(game_dir: Path, text: str) -> None:
    if not text:
        return
    path = persistent_game_log_path(game_dir)
    try:
        with path.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")
    except OSError:
        pass


def read_persistent_game_log(game_dir: Path) -> str:
    path = persistent_game_log_path(game_dir)
    if not path.is_file():
        return ""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > _MAX_DISPLAY_BYTES:
                handle.seek(size - _MAX_DISPLAY_BYTES)
            raw = handle.read()
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


class GameLogCollector:
    """Читает latest.log и дописывает в .launcher/game_log.txt (только добавление)."""

    def __init__(
        self,
        root: tk.Misc,
        *,
        get_game_dir: Callable[[], Path],
        get_shared_dir: Callable[[], Path],
    ) -> None:
        self._root = root
        self.get_game_dir = get_game_dir
        self.get_shared_dir = get_shared_dir
        self._latest_path: Path | None = None
        self._latest_pos = 0
        self._game_running = False
        self._listeners: list[Callable[[], None]] = []
        self._poll_job: str | None = None
        self._schedule_poll()

    def add_listener(self, callback: Callable[[], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def set_game_running(self, running: bool) -> None:
        if running and not self._game_running:
            self.mark_session_start()
        self._game_running = running

    def mark_session_start(self) -> None:
        game_dir = self.get_game_dir()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        append_game_log_line(
            game_dir,
            f"\n{'—' * 48}\n[{stamp}] Запуск Minecraft\n",
        )
        self._reset_latest_tail()

    def record_session_end(self, exit_code: int | None) -> None:
        game_dir = self.get_game_dir()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        code = "?" if exit_code is None else str(exit_code)
        append_game_log_line(
            game_dir,
            f"[{stamp}] Игра завершилась (код {code})\n",
        )
        self._sync_latest_log(force=True)
        self._notify()

    def _reset_latest_tail(self) -> None:
        game_dir = self.get_game_dir()
        shared = self.get_shared_dir()
        path, _hint = resolve_log_file(game_dir, shared)
        self._latest_path = path
        if path and path.is_file():
            try:
                self._latest_pos = path.stat().st_size
            except OSError:
                self._latest_pos = 0
        else:
            self._latest_pos = 0

    def _sync_latest_log(self, *, force: bool = False) -> None:
        game_dir = self.get_game_dir()
        shared = self.get_shared_dir()
        path, _hint = resolve_log_file(game_dir, shared)

        if path != self._latest_path:
            self._latest_path = path
            if path and path.is_file() and not force:
                try:
                    self._latest_pos = path.stat().st_size
                except OSError:
                    self._latest_pos = 0
            else:
                self._latest_pos = 0

        if not path or not path.is_file():
            return

        chunk, new_pos, _err = read_log_incremental(path, self._latest_pos)
        if new_pos != self._latest_pos:
            self._latest_pos = new_pos
        if chunk:
            try:
                with persistent_game_log_path(game_dir).open(
                    "a", encoding="utf-8", errors="replace"
                ) as handle:
                    handle.write(chunk)
            except OSError:
                pass
            self._notify()

    def _notify(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                pass

    def _schedule_poll(self) -> None:
        self._poll_job = self._root.after(300, self._poll)

    def _poll(self) -> None:
        if self._game_running:
            self._sync_latest_log()
        self._schedule_poll()

    def destroy(self) -> None:
        if self._poll_job:
            try:
                self._root.after_cancel(self._poll_job)
            except tk.TclError:
                pass
            self._poll_job = None
