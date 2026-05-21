"""Разбор дополнительных JVM-аргументов."""

from __future__ import annotations

import shlex


def parse_jvm_args(text: str) -> list[str]:
    raw = text.strip()
    if not raw:
        return []
    try:
        return shlex.split(raw, posix=False)
    except ValueError:
        return raw.split()


def join_jvm_args(args: list[str]) -> str:
    if not args:
        return ""
    return " ".join(args)
