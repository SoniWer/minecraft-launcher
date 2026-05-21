"""Лог событий лаунчера в launcher.log рядом с EXE."""

from __future__ import annotations

import logging
from pathlib import Path

_configured = False


def setup(launcher_dir: Path) -> None:
    global _configured
    if _configured:
        return
    path = launcher_dir / "launcher.log"
    logging.basicConfig(
        filename=str(path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    _configured = True


def info(message: str) -> None:
    logging.info(message)


def warning(message: str) -> None:
    logging.warning(message)


def error(message: str) -> None:
    logging.error(message)
