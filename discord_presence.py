"""Discord Rich Presence через локальный клиент Discord (pypresence, без ключей пользователя)."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_rpc: Any = None
_connected = False
_last_error = ""
_app_id_cache = ""


def _read_app_id_file(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        line = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except OSError:
        return ""
    if line.isdigit() and len(line) >= 17:
        return line
    return ""


def application_id() -> str:
    """Публичный Application ID лаунчера (вшит в EXE, не API-ключ)."""
    global _app_id_cache
    if _app_id_cache:
        return _app_id_cache

    for path in _app_id_paths():
        found = _read_app_id_file(path)
        if found:
            _app_id_cache = found
            return found

    try:
        from version import DISCORD_APPLICATION_ID

        cid = (DISCORD_APPLICATION_ID or "").strip()
    except ImportError:
        cid = ""
    if cid.isdigit() and len(cid) >= 17:
        _app_id_cache = cid
    return _app_id_cache


def _app_id_paths() -> list[Path]:
    paths: list[Path] = []
    if getattr(sys, "frozen", False):
        paths.append(Path(sys._MEIPASS) / "discord_application_id.txt")  # type: ignore[attr-defined]
    root = Path(__file__).resolve().parent
    paths.append(root / "discord_application_id.txt")
    return paths


def is_configured() -> bool:
    return bool(application_id())


def last_connect_error() -> str:
    return _last_error


def connect() -> bool:
    """Подключается к запущенному Discord (IPC). Ключи пользователя не нужны."""
    global _rpc, _connected, _last_error
    cid = application_id()
    if not cid:
        _last_error = "интеграция не настроена в этой сборке лаунчера"
        return False

    with _lock:
        disconnect()
        try:
            from pypresence import Presence  # type: ignore[import-untyped]
        except ImportError:
            _last_error = "модуль pypresence не установлен"
            return False

        last_exc: Exception | None = None
        for pipe in range(10):
            try:
                rpc = Presence(cid, pipe=pipe)
                rpc.connect()
                _rpc = rpc
                _connected = True
                _last_error = ""
                return True
            except Exception as exc:
                last_exc = exc
                continue

        if last_exc is not None:
            msg = str(last_exc).strip() or last_exc.__class__.__name__
            if "Could not connect" in msg or "pipe" in msg.lower():
                _last_error = "запустите Discord на этом компьютере"
            else:
                _last_error = msg
        else:
            _last_error = "не удалось подключиться к Discord"
        return False


def disconnect() -> None:
    global _rpc, _connected
    with _lock:
        if _rpc is not None:
            try:
                _rpc.clear()
            except Exception:
                pass
            try:
                _rpc.close()
            except Exception:
                pass
        _rpc = None
        _connected = False


def is_connected() -> bool:
    return _connected


def _update(**kwargs: Any) -> None:
    with _lock:
        if not _rpc:
            return
        try:
            _rpc.update(**kwargs)
        except Exception:
            pass


def set_idle(*, version: str) -> None:
    _update(
        details="Minecraft Launcher",
        state=f"v{version} · в меню",
        large_image="minecraft",
        large_text="Minecraft Launcher",
    )


def set_playing(
    *,
    build_name: str,
    mc_version: str,
    loader: str,
) -> None:
    loader_label = loader if loader and loader != "vanilla" else "Vanilla"
    _update(
        details=build_name[:128] or "Сборка",
        state=f"Minecraft {mc_version} · {loader_label}"[:128],
        large_image="minecraft",
        large_text="Играет в Minecraft",
    )


def set_installing(*, task: str) -> None:
    _update(
        details="Minecraft Launcher",
        state=task[:128],
        large_image="minecraft",
        large_text="Установка",
    )


def connect_async(on_done: Any | None = None) -> None:
    """connect() в фоне; on_done(success: bool)."""

    def worker() -> None:
        ok = connect()
        if on_done:
            on_done(ok)

    threading.Thread(target=worker, daemon=True).start()
