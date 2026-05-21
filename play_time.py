"""Учёт времени в игре."""

from __future__ import annotations


def format_play_time(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    rest = minutes % 60
    if rest:
        return f"{hours} ч {rest} мин"
    return f"{hours} ч"
