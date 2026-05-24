"""Открытие и чтение логов и crash-reports сборки."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _newest_log_in(log_dir: Path) -> Path | None:
    if not log_dir.is_dir():
        return None
    logs = [p for p in log_dir.glob("*.log") if p.is_file()]
    if not logs:
        return None
    return max(logs, key=lambda p: p.stat().st_mtime)


def resolve_log_file(game_dir: Path, shared_dir: Path | None = None) -> tuple[Path | None, str]:
    """Найти актуальный лог: сборка → .minecraft, latest.log или новейший *.log."""
    bases: list[Path] = [game_dir.resolve()]
    if shared_dir is not None:
        shared = Path(shared_dir).resolve()
        if shared not in bases:
            bases.append(shared)

    for base in bases:
        latest = base / "logs" / "latest.log"
        if latest.is_file():
            return latest, f"{latest.parent.name}/{latest.name}"

    for base in bases:
        found = _newest_log_in(base / "logs")
        if found is not None:
            return found, f"{found.parent.name}/{found.name}"

    for base in bases:
        log_dir = base / "logs"
        if log_dir.is_dir():
            return None, f"Ждём лог в {log_dir}"

    return None, "Папка logs/ появится после запуска MC"


def latest_log(game_dir: Path, shared_dir: Path | None = None) -> Path | None:
    path, _hint = resolve_log_file(game_dir, shared_dir)
    return path


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


_FATAL_MARKERS = (
    "fatal error",
    "game crashed",
    "crash report",
    "exception in thread",
    "fabric-loader",
    "modlauncher",
    "mixin apply",
    "process exited with code",
)


def log_issue_key(path: Path) -> str:
    try:
        return f"log:{path.resolve()}:{int(path.stat().st_mtime)}"
    except OSError:
        return f"log:{path}"


def log_has_fatal_tail(path: Path, *, tail_bytes: int = 48_000) -> bool:
    if not path.is_file():
        return False
    try:
        size = path.stat().st_size
        with open(path, "rb") as handle:
            handle.seek(max(0, size - tail_bytes))
            raw = handle.read()
        text = raw.decode("utf-8", errors="replace").lower()
    except OSError:
        return False
    return any(marker in text for marker in _FATAL_MARKERS)


def read_log_tail(path: Path, *, max_bytes: int = 96_000) -> str:
    if not path.is_file():
        return ""
    try:
        size = path.stat().st_size
        with open(path, "rb") as handle:
            handle.seek(max(0, size - max_bytes))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def latest_crash_report(game_dir: Path) -> Path | None:
    reports = list_crash_reports(game_dir)
    if not reports:
        return None
    return reports[0][0]


def list_crash_reports(game_dir: Path) -> list[tuple[Path, float, int]]:
    """(путь, mtime, размер_КБ) — от новых к старым."""
    folder = game_dir / "crash-reports"
    if not folder.is_dir():
        return []
    reports = [p for p in folder.glob("*.txt") if p.is_file()]
    reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[tuple[Path, float, int]] = []
    for path in reports:
        try:
            st = path.stat()
            out.append((path, st.st_mtime, max(1, st.st_size // 1024)))
        except OSError:
            continue
    return out


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
