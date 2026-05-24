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
_public_key_cache = ""

# Public Key приложения (не подставляется в pypresence — только для справки/сборки).
DISCORD_PUBLIC_KEY = (
    "b6fb7832f5c0e666d1eeb12a34e1164ee409d6e59e73fca37fcf2a52e4f1e9ff"
)


def _valid_application_id(value: str) -> str:
    value = value.strip()
    if value.isdigit() and 17 <= len(value) <= 20:
        return value
    return ""


def _read_app_id_file(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        line = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except OSError:
        return ""
    return _valid_application_id(line)


def _read_app_json(path: Path) -> tuple[str, str]:
    if not path.is_file():
        return "", ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    app_id = _valid_application_id(str(data.get("application_id") or ""))
    public_key = str(data.get("public_key") or "").strip().lower()
    if len(public_key) == 64 and all(c in "0123456789abcdef" for c in public_key):
        return app_id, public_key
    return app_id, ""


def _credential_paths() -> list[Path]:
    paths: list[Path] = []
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        paths.extend(
            [
                base / "discord_app.json",
                base / "discord_application_id.txt",
                base / "discord_public_key.txt",
            ]
        )
    root = Path(__file__).resolve().parent
    paths.extend(
        [
            root / "discord_app.json",
            root / "discord_application_id.txt",
            root / "discord_public_key.txt",
        ]
    )
    return paths


def public_key() -> str:
    global _public_key_cache
    if _public_key_cache:
        return _public_key_cache
    for path in _credential_paths():
        if path.name == "discord_app.json":
            _, pk = _read_app_json(path)
            if pk:
                _public_key_cache = pk
                return pk
        if path.name == "discord_public_key.txt" and path.is_file():
            try:
                line = path.read_text(encoding="utf-8").strip().splitlines()[0].strip().lower()
            except OSError:
                continue
            if len(line) == 64:
                _public_key_cache = line
                return line
    _public_key_cache = DISCORD_PUBLIC_KEY
    return _public_key_cache


def application_id() -> str:
    """Application ID (только цифры). Public Key для Rich Presence не подходит."""
    global _app_id_cache
    if _app_id_cache:
        return _app_id_cache

    for path in _credential_paths():
        if path.name == "discord_app.json":
            app_id, _ = _read_app_json(path)
            if app_id:
                _app_id_cache = app_id
                return app_id
        if path.name == "discord_application_id.txt":
            found = _read_app_id_file(path)
            if found:
                _app_id_cache = found
                return found

    try:
        from version import DISCORD_APPLICATION_ID

        cid = _valid_application_id(DISCORD_APPLICATION_ID or "")
    except ImportError:
        cid = ""
    if cid:
        _app_id_cache = cid
    return _app_id_cache


def is_configured() -> bool:
    return bool(application_id())


def configuration_hint() -> str:
    if is_configured():
        return ""
    if public_key() and not application_id():
        return (
            "В discord.com/developers у приложения скопируйте Application ID "
            "(цифры), а не Public Key."
        )
    return "Application ID не вшит в эту сборку лаунчера."


def last_connect_error() -> str:
    return _last_error


def connect() -> bool:
    """Подключается к запущенному Discord (IPC)."""
    global _rpc, _connected, _last_error
    cid = application_id()
    if not cid:
        hint = configuration_hint()
        _last_error = hint or "не задан Application ID"
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
    def worker() -> None:
        ok = connect()
        if on_done:
            on_done(ok)

    threading.Thread(target=worker, daemon=True).start()
