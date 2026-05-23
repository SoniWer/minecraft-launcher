"""Отслеживание запущенного процесса Minecraft."""

from __future__ import annotations

import subprocess
import time
import tkinter as tk
from collections.abc import Callable


class GameProcessTracker:
    def __init__(
        self,
        on_status: Callable[[bool], None],
        *,
        on_session_end: Callable[..., None] | None = None,
    ) -> None:
        self._on_status = on_status
        self._on_session_end = on_session_end
        self._process: subprocess.Popen[bytes] | None = None
        self._poll_job: str | None = None
        self._root = None
        self._started_at: float | None = None

    def bind_root(self, root) -> None:
        self._root = root

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process
        self._started_at = time.monotonic()
        self._schedule_poll()

    def kill(self) -> bool:
        proc = self._process
        if not proc or proc.poll() is not None:
            self._process = None
            self._started_at = None
            self._on_status(False)
            return False
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        self._finish_session()
        return True

    def _finish_session(self) -> None:
        proc = self._process
        self._process = None
        started = self._started_at
        self._started_at = None
        self._on_status(False)
        exit_code: int | None = None
        if proc is not None:
            try:
                exit_code = proc.poll()
            except Exception:
                exit_code = None
        if started is not None and self._on_session_end is not None:
            elapsed = max(0, int(time.monotonic() - started))
            if elapsed > 0:
                try:
                    self._on_session_end(elapsed, exit_code)
                except TypeError:
                    self._on_session_end(elapsed)

    def _schedule_poll(self) -> None:
        if self._root is None:
            return
        if self._poll_job:
            try:
                self._root.after_cancel(self._poll_job)
            except tk.TclError:
                pass
        self._poll_job = self._root.after(2000, self._poll)

    def _poll(self) -> None:
        self._poll_job = None
        proc = self._process
        if proc is None:
            self._on_status(False)
            return
        if proc.poll() is None:
            self._on_status(True)
            self._schedule_poll()
        else:
            self._finish_session()
