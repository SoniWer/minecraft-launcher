"""Фоновые задачи с безопасным обновлением UI."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def run_background(
    root,
    worker: Callable[[], T],
    on_result: Callable[[T], None],
    *,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    def task() -> None:
        try:
            result = worker()
            root.after(0, lambda r=result: on_result(r))
        except Exception as exc:
            if on_error is not None:
                root.after(0, lambda e=exc: on_error(e))
            else:
                root.after(0, lambda e=exc: _default_error(root, e))

    threading.Thread(target=task, daemon=True).start()


def _default_error(root, exc: Exception) -> None:
    if hasattr(root, "winfo_toplevel"):
        top = root.winfo_toplevel()
        if hasattr(top, "status_var"):
            top.status_var.set(f"Ошибка: {exc}")  # type: ignore[attr-defined]
