"""Сортировка списка версий Minecraft."""

from __future__ import annotations


def sort_with_favorites(version_ids: list[str], favorites: list[str]) -> list[str]:
    if not favorites:
        return version_ids
    fav_order = [v for v in favorites if v in version_ids]
    rest = [v for v in version_ids if v not in favorites]
    return fav_order + rest
