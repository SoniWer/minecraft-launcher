"""Лог событий лаунчера в launcher.log рядом с EXE."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_configured = False
_log_path: Path | None = None


def log_file_path(launcher_dir: Path) -> Path:
    return launcher_dir / "launcher.log"


def setup(launcher_dir: Path) -> None:
    global _configured, _log_path
    if _configured:
        return
    _log_path = log_file_path(launcher_dir)
    logging.basicConfig(
        filename=str(_log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    _configured = True

    def _hook(exc_type, exc: BaseException, tb) -> None:
        logging.error("Uncaught %s: %s", exc_type.__name__, exc)
        if sys.__excepthook__ is not _hook:
            sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def info(message: str) -> None:
    logging.info(message)


def warning(message: str) -> None:
    logging.warning(message)


def error(message: str) -> None:
    logging.error(message)
