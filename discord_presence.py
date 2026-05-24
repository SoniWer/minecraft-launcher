"""Discord Rich Presence (опционально, через pypresence)."""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_rpc: Any = None
_connected = False
_client_id = ""


def _resolve_client_id(settings_id: str) -> str:
    return (settings_id or "").strip()


def connect(client_id: str) -> bool:
    """Подключается к Discord. client_id — Application ID из Developer Portal."""
    global _rpc, _connected, _client_id
    cid = _resolve_client_id(client_id)
    if not cid:
        return False
    with _lock:
        disconnect()
        try:
            from pypresence import Presence  # type: ignore[import-untyped]
        except ImportError:
            return False
        try:
            rpc = Presence(cid)
            rpc.connect()
        except Exception:
            return False
        _rpc = rpc
        _connected = True
        _client_id = cid
        return True


def disconnect() -> None:
    global _rpc, _connected, _client_id
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
        _client_id = ""


def is_connected() -> bool:
    return _connected


def set_idle(*, version: str) -> None:
    with _lock:
        if not _rpc:
            return
        try:
            _rpc.update(
                details="Minecraft Launcher",
                state=f"v{version} · в меню",
                large_image="minecraft",
                large_text="Minecraft Launcher",
            )
        except Exception:
            pass


def set_playing(
    *,
    build_name: str,
    mc_version: str,
    loader: str,
) -> None:
    loader_label = loader if loader and loader != "vanilla" else "Vanilla"
    with _lock:
        if not _rpc:
            return
        try:
            _rpc.update(
                details=build_name[:128] or "Сборка",
                state=f"Minecraft {mc_version} · {loader_label}"[:128],
                large_image="minecraft",
                large_text="Играет в Minecraft",
            )
        except Exception:
            pass


def set_installing(*, task: str) -> None:
    with _lock:
        if not _rpc:
            return
        try:
            _rpc.update(
                details="Minecraft Launcher",
                state=task[:128],
                large_image="minecraft",
                large_text="Установка",
            )
        except Exception:
            pass
