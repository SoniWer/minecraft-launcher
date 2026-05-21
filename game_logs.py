"""Открытие и чтение логов и crash-reports сборки."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def latest_log(game_dir: Path) -> Path | None:
    path = game_dir / "logs" / "latest.log"
    return path if path.is_file() else None


def read_log_incremental(
    path: Path,
    position: int,
    *,
    max_bytes: int = 96_000,
) -> tuple[str, int, str | None]:
    """Дочитать лог с position. Возвращает (текст, новая_позиция, ошибка)."""
    if not path.is_file():
        return "", 0, None
    try:
        size = path.stat().st_size
    except OSError as exc:
        return "", position, str(exc)

    if size < position:
        position = 0
    if size <= position:
        return "", position, None

    to_read = min(size - position, max_bytes)
    try:
        with open(path, "rb") as handle:
            handle.seek(position)
            raw = handle.read(to_read)
        return raw.decode("utf-8", errors="replace"), position + len(raw), None
    except OSError:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if position > len(text):
                position = 0
            chunk = text[position : position + max_bytes]
            return chunk, position + len(chunk), None
        except OSError as exc:
            return "", position, str(exc)


def latest_crash_report(game_dir: Path) -> Path | None:
    folder = game_dir / "crash-reports"
    if not folder.is_dir():
        return None
    reports = [p for p in folder.glob("*.txt") if p.is_file()]
    if not reports:
        return None
    return max(reports, key=lambda p: p.stat().st_mtime)


def open_file(path: Path) -> None:
    target = path.resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Файл не найден: {target}")
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", target], check=False)
    else:
        subprocess.run(["xdg-open", target], check=False)
