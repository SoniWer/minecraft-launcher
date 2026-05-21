"""Иконки меню и логотип лаунчера (Pillow → PhotoImage)."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from theme import ThemeColors

_ICON_CACHE: dict[tuple[str, int, bool], tk.PhotoImage] = {}


def _pillow():
    from PIL import Image, ImageDraw

    return Image, ImageDraw


def _photo(img, master: tk.Misc | None = None) -> tk.PhotoImage:
    from PIL import ImageTk

    return ImageTk.PhotoImage(img)


def render_launcher_logo(size: int = 128, *, master: tk.Misc | None = None) -> tk.PhotoImage:
    key = ("logo", size, True)
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


def _icon_mod(size: int, colors: ThemeColors):
    Image, ImageDraw = _pillow()
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, size - 2, size - 2), radius=4, fill=colors.accent)
    d.rectangle((size // 4, size // 3, 3 * size // 4, 2 * size // 3), fill=colors.accent_fg)
    return img


def _icon_texture(size: int, colors: ThemeColors):
    Image, ImageDraw = _pillow()
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(4):
        for j in range(4):
            c = (90, 150, 200, 255) if (i + j) % 2 == 0 else (200, 120, 80, 255)
            d.rectangle(
                (2 + i * (size - 4) // 4, 2 + j * (size - 4) // 4,
                 2 + (i + 1) * (size - 4) // 4, 2 + (j + 1) * (size - 4) // 4),
                fill=c,
            )
    return img


def _icon_shader(size: int, colors: ThemeColors):
    Image, ImageDraw = _pillow()
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, size - 2, size - 2), fill=(120, 80, 200, 255))
    d.polygon(
        [(size // 2, size // 5), (4 * size // 5, 4 * size // 5), (size // 5, 4 * size // 5)],
        fill=(220, 200, 255, 230),
    )
    return img


def get_menu_icons(root: tk.Misc, colors: ThemeColors, *, size: int = 18) -> dict[str, tk.PhotoImage]:
    """Иконки для пунктов меню «Контент» (хранить ссылку на root)."""
    dark = getattr(root, "_launcher_dark", True)
    cache_key = ("menu", size, dark)
    if hasattr(root, "_launcher_menu_icons") and root._launcher_menu_icons_key == cache_key:  # type: ignore[attr-defined]
        return root._launcher_menu_icons  # type: ignore[attr-defined]

    makers = {
        "mods": _icon_mod,
        "textures": _icon_texture,
        "shaders": _icon_shader,
    }
    icons: dict[str, tk.PhotoImage] = {}
    for name, maker in makers.items():
        key = (name, size, dark)
        if key in _ICON_CACHE:
            icons[name] = _ICON_CACHE[key]
            continue
        img = maker(size, colors)
        photo = _photo(img, root)
        _ICON_CACHE[key] = photo
        icons[name] = photo

    root._launcher_menu_icons = icons  # type: ignore[attr-defined]
    root._launcher_menu_icons_key = cache_key  # type: ignore[attr-defined]
    return icons
