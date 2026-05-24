"""Discord Rich Presence через локальный клиент Discord (pypresence)."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

CONNECT_TIMEOUT_SEC = 2.5
PIPE_TRIES = 4

_lock = threading.Lock()
_rpc: Any = None
_connected = False
_last_error = ""
_app_id_cache = ""
_cancel_connect = threading.Event()
_shutting_down = False


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


def _safe_close(rpc: Any) -> None:
    if rpc is None:
        return
    try:
        rpc.clear()
    except Exception:
        pass
    try:
        rpc.close()
    except Exception:
        pass


def _connect_rpc(rpc: Any, *, timeout: float) -> bool:
    """rpc.connect() с таймаутом (не держит глобальный lock)."""
    done = threading.Event()
    error: list[BaseException] = []

    def run() -> None:
        try:
            rpc.connect()
        except BaseException as exc:
            error.append(exc)
        finally:
            done.set()

    threading.Thread(target=run, daemon=True).start()
    if not done.wait(timeout):
        return False
    if error:
        raise error[0]
    return True


def cancel_connect() -> None:
    _cancel_connect.set()


def shutdown() -> None:
    global _shutting_down
    _shutting_down = True
    _cancel_connect.set()
    disconnect()


def connect() -> bool:
    global _rpc, _connected, _last_error
    if _shutting_down or _cancel_connect.is_set():
        return False

    cid = application_id()
    if not cid:
        _last_error = "не задан Application ID"
        return False

    try:
        from pypresence import Presence  # type: ignore[import-untyped]
    except ImportError:
        _last_error = "модуль pypresence не установлен"
        return False

    last_exc: BaseException | None = None
    timed_out = False

    for pipe in range(PIPE_TRIES):
        if _shutting_down or _cancel_connect.is_set():
            _last_error = "отменено"
            return False

        rpc = None
        try:
            rpc = Presence(cid, pipe=pipe)
            if not _connect_rpc(rpc, timeout=CONNECT_TIMEOUT_SEC):
                timed_out = True
                _safe_close(rpc)
                continue
            with _lock:
                if _shutting_down or _cancel_connect.is_set():
                    _safe_close(rpc)
                    _last_error = "отменено"
                    return False
                old = _rpc
                _rpc = rpc
                _connected = True
                _last_error = ""
            _safe_close(old)
            return True
        except Exception as exc:
            last_exc = exc
            _safe_close(rpc)

    if timed_out and last_exc is None:
        _last_error = "таймаут: запустите Discord на этом компьютере"
    elif last_exc is not None:
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
        _safe_close(_rpc)
        _rpc = None
        _connected = False


def is_connected() -> bool:
    return _connected


def _update(**kwargs: Any) -> None:
    if _shutting_down or not _connected:
        return
    with _lock:
        rpc = _rpc
    if not rpc:
        return
    try:
        rpc.update(**kwargs)
    except Exception:
        pass


def set_idle(*, version: str) -> None:
    _update(
        details="Minecraft Launcher",
        state=f"v{version} · в меню",
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
    )


def set_installing(*, task: str) -> None:
    _update(
        details="Minecraft Launcher",
        state=task[:128],
    )


def connect_async(on_done: Any | None = None) -> None:
    global _shutting_down
    _shutting_down = False
    _cancel_connect.clear()

    def worker() -> None:
        ok = connect()
        if on_done and not _shutting_down:
            on_done(ok)

    threading.Thread(target=worker, daemon=True).start()
