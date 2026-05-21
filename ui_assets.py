"""Логотип лаунчера для заставки."""

from __future__ import annotations

import tkinter as tk

_ICON_CACHE: dict[tuple[str, int], tk.PhotoImage] = {}


def _pillow():
    from PIL import Image, ImageDraw

    return Image, ImageDraw


def _photo(img, master: tk.Misc | None = None) -> tk.PhotoImage:
    from PIL import ImageTk

    return ImageTk.PhotoImage(img, master=master)


def render_launcher_logo(size: int = 128, *, master: tk.Misc | None = None) -> tk.PhotoImage:
    key = ("logo", size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    Image, ImageDraw = _pillow()
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = size / 256
    draw.rounded_rectangle(
        (16 * m, 16 * m, 240 * m, 240 * m), radius=28 * m, fill=(61, 142, 74, 255)
    )
    draw.rounded_rectangle(
        (24 * m, 24 * m, 232 * m, 232 * m), radius=22 * m, fill=(86, 168, 96, 255)
    )
    draw.rectangle((78 * m, 72 * m, 98 * m, 188 * m), fill=(240, 240, 240, 255))
    draw.rectangle((158 * m, 72 * m, 178 * m, 188 * m), fill=(240, 240, 240, 255))
    draw.polygon(
        [
            (98 * m, 72 * m),
            (128 * m, 120 * m),
            (158 * m, 72 * m),
            (148 * m, 72 * m),
            (128 * m, 108 * m),
            (108 * m, 72 * m),
        ],
        fill=(240, 240, 240, 255),
    )
    photo = _photo(img, master)
    _ICON_CACHE[key] = photo
    return photo
