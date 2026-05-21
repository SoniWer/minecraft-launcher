"""Перетаскивание .jar в окно лаунчера (Windows)."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path


def copy_jar_files(paths: list[str], mods_dir: Path) -> list[str]:
    mods_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            continue
        lower = path.name.lower()
        if not lower.endswith(".jar"):
            continue
        dest = mods_dir / path.name
        if dest.resolve() == path.resolve():
            continue
        if dest.exists():
            stem = path.stem
            dest = mods_dir / f"{stem}-imported{path.suffix}"
            n = 2
            while dest.exists():
                dest = mods_dir / f"{stem}-imported-{n}{path.suffix}"
                n += 1
        shutil.copy2(path, dest)
        copied.append(dest.name)
    return copied


def enable_jar_drop(
    window,
    mods_dir: Callable[[], Path],
    *,
    on_copied: Callable[[list[str]], None] | None = None,
) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import windnd
    except ImportError:
        return False

    def _decode(item) -> str:
        if isinstance(item, bytes):
            return item.decode("utf-8", errors="replace")
        return str(item)

    def _on_drop(files) -> None:
        paths = [_decode(f) for f in files]
        copied = copy_jar_files(paths, mods_dir())
        if copied and on_copied:
            on_copied(copied)

    try:
        windnd.hook_dropfiles(window, func=_on_drop)
        return True
    except Exception:
        return False
