"""Иконки сборок (цвет + буква) для списка в лаунчере."""

from __future__ import annotations

import hashlib
from pathlib import Path

from builds import Build

ICON_NAME = "build_icon.png"
SIZE = 32

_PALETTE = (
    "#5b8def",
    "#4caf82",
    "#e8a838",
    "#c77dff",
    "#ef6b6b",
    "#3db8c4",
    "#9e9e9e",
)


def icon_path(build: Build, launcher_dir: Path) -> Path:
    return build.root(launcher_dir) / ICON_NAME


def _pick_color(name: str) -> str:
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return _PALETTE[int(digest[:8], 16) % len(_PALETTE)]


def ensure_build_icon(build: Build, launcher_dir: Path) -> Path:
    path = icon_path(build, launcher_dir)
    if path.is_file():
        return path
    build.root(launcher_dir).mkdir(parents=True, exist_ok=True)
    letter = (build.name.strip()[:1] or "?").upper()
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return path

    color = _pick_color(build.name)
    img = Image.new("RGBA", (SIZE, SIZE), color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("segoeui.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((SIZE - tw) / 2, (SIZE - th) / 2 - 1),
        letter,
        fill="#ffffff",
        font=font,
    )
    img.save(path, format="PNG")
    return path
