"""Иконки проектов Modrinth (загрузка в фоне, отображение в UI-потоке)."""

from __future__ import annotations

import io
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

import requests

from modrinth import USER_AGENT

if TYPE_CHECKING:
    import tkinter as tk
    from PIL import Image

_BYTES_CACHE: dict[str, bytes] = {}
_CACHE_LOCK = threading.Lock()
_MAX_CACHE = 384
_ICON_WORKERS = 16
_ICON_TIMEOUT = 8


def _fetch_bytes(url: str) -> bytes | None:
    if not url or not url.startswith("http"):
        return None
    with _CACHE_LOCK:
        if url in _BYTES_CACHE:
            return _BYTES_CACHE[url]
    try:
        resp = requests.get(
            url, timeout=_ICON_TIMEOUT, headers={"User-Agent": USER_AGENT}
        )
        if resp.status_code != 200:
            return None
        data = resp.content
    except requests.RequestException:
        return None
    with _CACHE_LOCK:
        if len(_BYTES_CACHE) >= _MAX_CACHE:
            _BYTES_CACHE.pop(next(iter(_BYTES_CACHE)))
        _BYTES_CACHE[url] = data
    return data


def fetch_icon_rgba(url: str | None, *, size: int = 28) -> Any | None:
    """PIL.Image RGBA — можно вызывать из фонового потока."""
    raw = _fetch_bytes(url) if url else None
    if not raw:
        return _placeholder_rgba(size)
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        return img.resize((size, size), Image.Resampling.LANCZOS)
    except Exception:
        return _placeholder_rgba(size)


def _placeholder_rgba(size: int) -> Any:
    from PIL import Image

    return Image.new("RGBA", (size, size), (80, 80, 90, 255))


def icon_photo_from_rgba(img: Any, master: "tk.Misc") -> "tk.PhotoImage | None":
    """Создать PhotoImage только из главного потока Tk."""
    try:
        from PIL import ImageTk

        return ImageTk.PhotoImage(img, master=master)
    except Exception:
        return None


def load_icons_batch(
    items: list[tuple[str, str | None]],
    *,
    size: int = 28,
    on_done: Callable[[list[tuple[str, Any]]], None],
) -> None:
    """Параллельная загрузка иконок; on_done — из фонового потока."""

    def worker() -> None:
        out: list[tuple[str, Any]] = []

        def load_one(item: tuple[str, str | None]) -> tuple[str, Any]:
            iid, url = item
            return iid, fetch_icon_rgba(url, size=size)

        with ThreadPoolExecutor(max_workers=_ICON_WORKERS) as pool:
            futures = {pool.submit(load_one, item): item for item in items}
            for future in as_completed(futures):
                try:
                    out.append(future.result())
                except Exception:
                    iid, _url = futures[future]
                    out.append((iid, fetch_icon_rgba(None, size=size)))
        on_done(out)

    threading.Thread(target=worker, daemon=True).start()
