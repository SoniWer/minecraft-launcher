"""Рекомендации по ОЗУ для сборки."""

from __future__ import annotations

from pathlib import Path


def count_mod_jars(game_dir: Path) -> int:
    mods = game_dir / "mods"
    if not mods.is_dir():
        return 0
    return sum(
        1
        for path in mods.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".jar"
        and not path.name.lower().endswith(".disabled")
    )


def recommend_ram_gb(
    game_dir: Path,
    *,
    loader: str = "vanilla",
) -> int:
    mods = count_mod_jars(game_dir)
    if loader == "vanilla":
        base = 4
    elif loader in ("fabric", "quilt"):
        base = 6
    else:
        base = 8
    extra = mods // 12
    return min(32, max(2, base + extra))


def ram_hint_text(game_dir: Path, *, loader: str, current_gb: int) -> str:
    recommended = recommend_ram_gb(game_dir, loader=loader)
    mods = count_mod_jars(game_dir)
    parts = [f"Рекомендуется: {recommended} ГБ"]
    if mods:
        parts.append(f"модов: {mods}")
    if current_gb < recommended:
        parts.append("(сейчас мало)")
    return " · ".join(parts)
