"""Discord Rich Presence через локальный клиент Discord (pypresence)."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_rpc: Any = None
_connected = False
_last_error = ""
_app_id_cache = ""


def _valid_application_id(value: str) -> str:
    value = value.strip()
    if value.isdigit() and 17 <= len(value) <= 20:
        return value
    return ""


def _app_id_from_json(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if isinstance(data, dict):
        return _valid_application_id(str(data.get("application_id") or ""))
    return ""


def _app_id_from_txt(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        line = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except OSError:
        return ""
    return _valid_application_id(line)


def application_id() -> str:
    global _app_id_cache
    if _app_id_cache:
        return _app_id_cache

    try:
        from version import DISCORD_APPLICATION_ID

        cid = _valid_application_id(DISCORD_APPLICATION_ID or "")
        if cid:
            _app_id_cache = cid
            return cid
    except ImportError:
        pass

    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys._MEIPASS))  # type: ignore[attr-defined]
    roots.append(Path(__file__).resolve().parent)

    for root in roots:
        cid = _app_id_from_json(root / "discord_app.json")
        if cid:
            _app_id_cache = cid
            return cid
        cid = _app_id_from_txt(root / "discord_application_id.txt")
        if cid:
            _app_id_cache = cid
            return cid
    return ""


def is_configured() -> bool:
    return bool(application_id())


def last_connect_error() -> str:
    return _last_error


def connect() -> bool:
    global _rpc, _connected, _last_error
    cid = application_id()
    if not cid:
        _last_error = "не задан Application ID"
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
    def worker() -> None:
        ok = connect()
        if on_done:
            on_done(ok)

    threading.Thread(target=worker, daemon=True).start()
