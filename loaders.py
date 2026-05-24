"""Мод-загрузчики: id и подписи в интерфейсе."""

from __future__ import annotations

MOD_LOADERS: list[tuple[str, str]] = [
    ("vanilla", "Vanilla (без модов)"),
    ("fabric", "Fabric"),
    ("forge", "Forge"),
    ("neoforge", "NeoForge"),
    ("quilt", "Quilt"),
]

LOADER_BY_NAME = {display: lid for lid, display in MOD_LOADERS}
LOADER_DISPLAY = {lid: display for lid, display in MOD_LOADERS}
LOADER_LABELS = [display for _, display in MOD_LOADERS]
