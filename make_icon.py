#!/usr/bin/env python3
"""Создать launcher.ico для EXE (нужен Pillow: pip install pillow)."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise SystemExit("Установите Pillow: pip install pillow") from exc

    root = Path(__file__).resolve().parent
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Фон — «трава» Minecraft
    draw.rounded_rectangle((16, 16, 240, 240), radius=28, fill=(61, 142, 74, 255))
    draw.rounded_rectangle((
        24, 24, 232, 232
    ), radius=22, fill=(86, 168, 96, 255))

    # Буква M
    draw.rectangle((78, 72, 98, 188), fill=(240, 240, 240, 255))
    draw.rectangle((158, 72, 178, 188), fill=(240, 240, 240, 255))
    draw.polygon(
        [(98, 72), (128, 120), (158, 72), (148, 72), (128, 108), (108, 72)],
        fill=(240, 240, 240, 255),
    )

    ico_path = root / "launcher.ico"
    img.save(
        ico_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Created: {ico_path}")


if __name__ == "__main__":
    main()
