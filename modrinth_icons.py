"""Иконки проектов Modrinth для Treeview."""

from __future__ import annotations

import io
import tkinter as tk
from urllib.parse import urlparse

import requests

from modrinth import USER_AGENT

_ICON_CACHE: dict[str, tk.PhotoImage] = {}
_PLACEHOLDER: tk.PhotoImage | None = None


def _fetch_image_bytes(url: str) -> bytes | None:
    if not url or not url.startswith("http"):
        return None
    try:
        resp = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code != 200:
            return None
        return resp.content
    except requests.RequestException:
        return None


def get_modrinth_icon(
    url: str | None,
    *,
    master: tk.Misc,
    size: int = 32,
) -> tk.PhotoImage | None:
    """Загрузить иконку Modrinth (кэш по URL)."""
    global _PLACEHOLDER
    if not url:
        return _placeholder(master, size)

    key = f"{urlparse(url).path}@{size}"
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    raw = _fetch_image_bytes(url)
    if not raw:
        return _placeholder(master, size)

    try:
        from PIL import Image, ImageTk

        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img, master=master)
        _ICON_CACHE[key] = photo
        return photo
    except Exception:
        return _placeholder(master, size)


def _placeholder(master: tk.Misc, size: int) -> tk.PhotoImage | None:
    global _PLACEHOLDER
    try:
        from PIL import Image, ImageTk

        if _PLACEHOLDER is None:
            img = Image.new("RGBA", (size, size), (80, 80, 90, 255))
            _PLACEHOLDER = ImageTk.PhotoImage(img, master=master)
        return _PLACEHOLDER
    except Exception:
        return None
